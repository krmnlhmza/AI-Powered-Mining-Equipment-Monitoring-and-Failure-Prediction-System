"""
Model Eğitimi v2
════════════════
Çalıştırma:  .venv/bin/python ml/train.py

Tüm veriler data/simulator.py'deki fiziksel dijital ikizden, canlı akışla
AYNI motor ve AYNI okuma aralığıyla (3 sn) üretilir. Bölmeler daima MAKİNE
(birim) bazındadır: bir makinenin okumaları hem eğitimde hem doğrulamada
yer almaz (sızıntı yok).

Eğitilen modeller (ekipman tipi başına: loader / truck):
  1) Normal Davranış Modeli (NBM) — sağlıklı filo verisi
  2) Isolation Forest — NBM artıkları (z) üzerinde, skor kalibrasyonlu
  3) RUL LSTM (tipler ortak) — run-to-failure filosundan çalışma-saati
     özet dizileri → kalan ömür (saat) + arızalanacak bileşen
  4) Tahminci LSTM — son 20 okuma → 30 sn sonrası (5 sensör)

Çıktılar: ml/artifacts/
"""

from __future__ import annotations

import os
import pickle
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import numpy as np
import torch
import torch.nn as nn

from data.simulator import (COMPONENT_NAMES, EQUIPMENT_PROFILES, SENSORS,
                            STREAM_INTERVAL_S, simulate_streams)
from ml.features import (N_CTX, SNAP_DIM, TARGETS, NormalBehaviourModel,
                         baseline_correct_batch, residuals_batch, smooth_z_batch,
                         snapshots_batch, stream_context_batch, targets_batch)

ART = "ml/artifacts"
TYPE_EQ = {"loader": "LH517i_001", "truck": "TH551i_001"}   # tip → profil temsilcisi
DT = STREAM_INTERVAL_S

# RUL
RUL_CAP = 150.0          # saat — üstü "sağlıklı/uzak" (C-MAPSS'teki parçalı doğrusal etiket)
RUL_SEQ = 30             # özet sayısı (×4 sa = 120 çalışma saati geçmiş)
RUL_MIN_SNAPS = 4
N_COMP = len(COMPONENT_NAMES)
HEALTHY_CLASS = N_COMP   # sınıf indeksi: "yakın arıza yok"

# Tahminci
FC_FEATURES = ["temperature", "vibration", "pressure", "current", "speed"]
FC_SEQ = 20
FC_HORIZON = 10          # okuma (= 30 sn)

torch.set_num_threads(max(1, (os.cpu_count() or 2) // 2))


# ═════════════════════════════════════════════════════════════════
# Modeller
# ═════════════════════════════════════════════════════════════════
class RULNet(nn.Module):
    def __init__(self, in_dim: int, hidden: int = 64):
        super().__init__()
        self.lstm = nn.LSTM(in_dim, hidden, 2, batch_first=True, dropout=0.2)
        self.rul = nn.Sequential(nn.Linear(hidden, 32), nn.ReLU(), nn.Linear(32, 1))
        self.cls = nn.Sequential(nn.Linear(hidden, 32), nn.ReLU(), nn.Linear(32, N_COMP + 1))

    def forward(self, x):
        h = self.lstm(x)[0][:, -1]
        return torch.sigmoid(self.rul(h)).squeeze(-1), self.cls(h)


class ForecastNet(nn.Module):
    def __init__(self, n_feat: int = len(FC_FEATURES), hidden: int = 64):
        super().__init__()
        self.lstm = nn.LSTM(n_feat, hidden, 2, batch_first=True, dropout=0.1)
        self.fc = nn.Linear(hidden, n_feat)

    def forward(self, x):
        return self.fc(self.lstm(x)[0][:, -1])   # x_son'a göre değişim (ölçekli)


# ═════════════════════════════════════════════════════════════════
# Yardımcılar
# ═════════════════════════════════════════════════════════════════
def flat(a: np.ndarray, valid: np.ndarray | None = None) -> np.ndarray:
    if valid is None:
        return a.reshape(-1, a.shape[-1])
    return a[valid]


def calibrate(raw_healthy: np.ndarray, raw_anom: np.ndarray) -> dict:
    """Ham IF skorunu (x = −score_samples; büyük = anormal) 0-1'e haritalar.
    Çapalar: sağlıklı medyan → 0.10, sağlıklı %99 → 0.50, sağlıklı %99.9 → 0.60
    (yani 0.6 = 'binde bir sağlıklı okumanın aştığı seviye'), belirgin hasar
    (D ≥ 0.5) medyanı → 0.85."""
    q = np.quantile(raw_healthy, [0.5, 0.99, 0.999])
    x4 = max(float(np.median(raw_anom)), q[2] + 1e-6) if len(raw_anom) else q[2] + 1.0
    x5 = x4 + 2 * (x4 - q[2])
    return {"xp": [float(q[0]), float(q[1]), float(q[2]), x4, x5],
            "fp": [0.10, 0.50, 0.60, 0.85, 0.98]}


def apply_calibration(raw: np.ndarray, calib: dict) -> np.ndarray:
    return np.clip(np.interp(raw, calib["xp"], calib["fp"]), 0.0, 1.0)


def rul_windows(snaps: np.ndarray, rul: np.ndarray, comp: np.ndarray, is_truck: float):
    """Tek birimin özet dizisinden (pencere, etiket) çiftleri; sol dolgu = ilk özet."""
    X, yr, yc = [], [], []
    K = len(snaps)
    for k in range(RUL_MIN_SNAPS - 1, K):
        w = snaps[max(0, k - RUL_SEQ + 1):k + 1]
        if len(w) < RUL_SEQ:
            w = np.concatenate([np.repeat(w[:1], RUL_SEQ - len(w), 0), w])
        X.append(np.concatenate([w, np.full((RUL_SEQ, 1), is_truck)], 1))
        r = min(float(rul[k]), RUL_CAP)
        yr.append(r / RUL_CAP)
        yc.append(int(comp[k]) if rul[k] < RUL_CAP else HEALTHY_CLASS)
    return X, yr, yc


def build_rul_dataset(monitors: dict, n_units: int, seed: int, duration_s: float = 3600.0):
    """Her tip için run-to-failure filosu → RUL pencereleri (birim kimliğiyle)."""
    X, yr, yc, uid = [], [], [], []
    base = 0
    for t_i, (etype, eq) in enumerate(TYPE_EQ.items()):
        prof = EQUIPMENT_PROFILES[eq]
        mon = monitors[etype]
        s = simulate_streams(eq, n_units, duration_s, seed=seed + t_i, mode="run_to_failure")
        z, ctx = residuals_batch(mon["nbm"], s["X"], SENSORS, prof, DT)
        snaps = snapshots_batch(z, ctx, s["op_hours"], s["valid"])
        for u, (sn, ends) in enumerate(snaps):
            if len(sn) < RUL_MIN_SNAPS:
                continue
            a, b, c = rul_windows(sn, s["true_rul"][u, ends], s["true_comp"][u, ends],
                                  float(etype == "truck"))
            X += a; yr += b; yc += c; uid += [base + u] * len(a)
        base += n_units
    return (np.array(X, np.float32), np.array(yr, np.float32),
            np.array(yc, np.int64), np.array(uid))


# ═════════════════════════════════════════════════════════════════
# 1-2) NBM + Isolation Forest (tip başına)
# ═════════════════════════════════════════════════════════════════
def train_monitor(etype: str, seed: int = 0) -> dict:
    from sklearn.ensemble import IsolationForest
    eq = TYPE_EQ[etype]
    prof = EQUIPMENT_PROFILES[eq]
    t0 = time.time()
    h = simulate_streams(eq, 240, 3600, seed=seed, mode="healthy")
    ctx = stream_context_batch(h["X"], SENSORS, prof, DT)
    Y = targets_batch(h["X"], SENSORS)
    n = ctx.shape[0]
    A, B1, B2 = slice(0, n // 2), slice(n // 2, 3 * n // 4), slice(3 * n // 4, n)

    nbm = NormalBehaviourModel().fit(flat(ctx[A]), flat(Y[A]), flat(ctx[B1]), flat(Y[B1]))
    # σ'yı devreye alma düzeltmesinden SONRAKİ artıklara göre yeniden ölçekle
    # (makineye özgü sabit sapma çıkarıldıktan sonra kalan gerçek belirsizlik).
    zb = flat(baseline_correct_batch(nbm.z(flat(ctx[B1]), flat(Y[B1])).reshape(Y[B1].shape)))
    nbm.sigma = nbm.sigma * np.maximum(1.4826 * np.median(np.abs(zb - np.median(zb, 0)), 0), 1e-3)
    zs = lambda c, y: smooth_z_batch(baseline_correct_batch(
        nbm.z(c.reshape(-1, N_CTX), y.reshape(-1, len(TARGETS))).reshape(y.shape)), DT)
    z_b1, z_b2 = zs(ctx[B1], Y[B1]), zs(ctx[B2], Y[B2])

    iforest = IsolationForest(n_estimators=300, max_samples=2048, contamination="auto",
                              random_state=seed).fit(flat(z_b1))

    # Kalibrasyon: sağlıklı (görülmemiş B2) + belirgin hasarlı run-to-failure okumaları
    r = simulate_streams(eq, 80, 3600, seed=seed + 50, mode="run_to_failure")
    rc = stream_context_batch(r["X"], SENSORS, prof, DT)
    ry = targets_batch(r["X"], SENSORS)
    rz = zs(rc, ry)
    anom = rz[r["valid"] & (r["max_damage"] >= 0.5)]
    calib = calibrate(-iforest.score_samples(flat(z_b2)), -iforest.score_samples(anom))
    # İkinci dedektör: sensör başına artık kontrol limiti (max|z|). IF, TEK bir
    # sensördeki aşırı sapmada (ör. soğutma arızasında yalnız sıcaklık) doyar;
    # max|z| bunu yakalar. Aynı sağlıklı çapalarla kalibre edilir.
    calib_z = calibrate(np.abs(flat(z_b2)).max(1), np.abs(anom).max(1))

    s_h = np.maximum(apply_calibration(-iforest.score_samples(flat(z_b2)), calib),
                     apply_calibration(np.abs(flat(z_b2)).max(1), calib_z))
    print(f"  [{etype}] NBM σ = " + ", ".join(f"{k}:{s:.2f}" for k, s in zip(TARGETS, nbm.sigma))
          + f"   sağlıklı okuma ≥0.6: %{(s_h >= 0.6).mean()*100:.2f}   ({time.time()-t0:.0f} sn)")
    return {"nbm": nbm, "iforest": iforest, "calib": calib, "calib_z": calib_z, "type": etype,
            "profile_eq": eq, "dt": DT}


# ═════════════════════════════════════════════════════════════════
# 3) RUL LSTM
# ═════════════════════════════════════════════════════════════════
def train_rul(monitors: dict, seed: int = 0, epochs: int = 40):
    t0 = time.time()
    X, yr, yc, uid = build_rul_dataset(monitors, n_units=700, seed=seed + 100)
    units = np.unique(uid)
    rng = np.random.default_rng(seed)
    val_units = set(rng.choice(units, len(units) // 5, replace=False).tolist())
    vm = np.array([u in val_units for u in uid])

    mu = X[~vm].reshape(-1, X.shape[-1]).mean(0)
    sd = X[~vm].reshape(-1, X.shape[-1]).std(0) + 1e-6
    mu[-1], sd[-1] = 0.0, 1.0                                  # tip bayrağı ölçeklenmez
    Xn = np.clip((X - mu) / sd, -10, 10).astype(np.float32)
    print(f"  RUL pencereleri: eğitim {int((~vm).sum())}  doğrulama {int(vm.sum())}  "
          f"(birim: {len(units)})")

    model = RULNet(Xn.shape[-1])
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-5)
    sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, factor=0.5, patience=3)
    tr = torch.utils.data.TensorDataset(torch.tensor(Xn[~vm]), torch.tensor(yr[~vm]),
                                        torch.tensor(yc[~vm]))
    dl = torch.utils.data.DataLoader(tr, batch_size=256, shuffle=True)
    Xv, yrv, ycv = torch.tensor(Xn[vm]), torch.tensor(yr[vm]), torch.tensor(yc[vm])
    best, best_state, bad = 1e9, None, 0
    for ep in range(1, epochs + 1):
        model.train()
        for xb, rb, cb in dl:
            opt.zero_grad()
            pr, pc = model(xb)
            loss = nn.functional.mse_loss(pr, rb) + 0.05 * nn.functional.cross_entropy(pc, cb)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
        model.eval()
        with torch.no_grad():
            pr, pc = model(Xv)
            rmse = float(torch.sqrt(((pr - yrv) ** 2).mean())) * RUL_CAP
            acc = float((pc.argmax(1) == ycv).float().mean())
        sched.step(rmse)
        if rmse < best - 0.05:
            best, best_state, bad = rmse, {k: v.clone() for k, v in model.state_dict().items()}, 0
        else:
            bad += 1
        if ep % 5 == 0 or bad == 0:
            print(f"  epoch {ep:3d}  doğrulama RMSE {rmse:6.2f} sa   bileşen doğruluğu %{acc*100:4.1f}")
        if bad >= 8:
            break
    model.load_state_dict(best_state)
    torch.save(model.state_dict(), f"{ART}/rul_lstm.pt")
    with open(f"{ART}/rul_meta.pkl", "wb") as f:
        pickle.dump({"mu": mu, "sd": sd, "cap": RUL_CAP, "seq": RUL_SEQ,
                     "min_snaps": RUL_MIN_SNAPS, "components": COMPONENT_NAMES,
                     "in_dim": int(Xn.shape[-1]), "val_rmse": best}, f)
    print(f"  RUL modeli kaydedildi (en iyi doğrulama RMSE {best:.2f} sa, {time.time()-t0:.0f} sn)")


# ═════════════════════════════════════════════════════════════════
# 4) Tahminci LSTM (tip başına)
# ═════════════════════════════════════════════════════════════════
def forecast_windows(X: np.ndarray, valid: np.ndarray | None, stride: int = 2):
    idx = [SENSORS.index(k) for k in FC_FEATURES]
    xs, ys = [], []
    for u in range(X.shape[0]):
        T = X.shape[1] if valid is None else int(valid[u].sum())
        a = X[u, :T][:, idx]
        for t in range(FC_SEQ, T - FC_HORIZON + 1, stride):
            xs.append(a[t - FC_SEQ:t])
            ys.append(a[t + FC_HORIZON - 1])
    return np.array(xs, np.float32), np.array(ys, np.float32)


def train_forecaster(etype: str, seed: int = 0, epochs: int = 25):
    t0 = time.time()
    eq = TYPE_EQ[etype]
    h = simulate_streams(eq, 120, 2400, seed=seed + 200, mode="healthy")
    r = simulate_streams(eq, 80, 3600, seed=seed + 300, mode="run_to_failure")
    xa, ya = forecast_windows(h["X"], None)
    xb, yb = forecast_windows(r["X"], r["valid"], stride=4)
    X, Y = np.concatenate([xa, xb]), np.concatenate([ya, yb])
    mu, sd = X.reshape(-1, X.shape[-1]).mean(0), X.reshape(-1, X.shape[-1]).std(0) + 1e-6
    Xn = (X - mu) / sd
    dY = (Y - X[:, -1]) / sd                     # hedef: son okumaya göre değişim
    n = len(Xn)
    perm = np.random.default_rng(seed).permutation(n)
    tr, va = perm[: int(n * 0.9)], perm[int(n * 0.9):]
    model = ForecastNet()
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    dl = torch.utils.data.DataLoader(torch.utils.data.TensorDataset(
        torch.tensor(Xn[tr]), torch.tensor(dY[tr])), batch_size=512, shuffle=True)
    Xv, Yv = torch.tensor(Xn[va]), torch.tensor(dY[va])
    best, best_state = 1e9, None
    for ep in range(1, epochs + 1):
        model.train()
        for xb_, yb_ in dl:
            opt.zero_grad()
            loss = nn.functional.mse_loss(model(xb_), yb_)
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            v = float(nn.functional.mse_loss(model(Xv), Yv))
        if v < best:
            best, best_state = v, {k: t.clone() for k, t in model.state_dict().items()}
    model.load_state_dict(best_state)
    torch.save(model.state_dict(), f"{ART}/forecast_{etype}.pt")
    with open(f"{ART}/forecast_{etype}_meta.pkl", "wb") as f:
        pickle.dump({"mu": mu, "sd": sd, "features": FC_FEATURES, "seq": FC_SEQ,
                     "horizon": FC_HORIZON, "dt": DT}, f)
    print(f"  [{etype}] tahminci kaydedildi (doğrulama MSE {best:.4f}, {time.time()-t0:.0f} sn)")


def main():
    os.makedirs(ART, exist_ok=True)
    np.random.seed(0)
    torch.manual_seed(0)
    print("── 1-2) Normal davranış modeli + Isolation Forest ──")
    monitors = {}
    for i, etype in enumerate(TYPE_EQ):
        monitors[etype] = train_monitor(etype, seed=10 * i)
        with open(f"{ART}/monitor_{etype}.pkl", "wb") as f:
            pickle.dump(monitors[etype], f)
    print("\n── 3) RUL LSTM (kalan ömür + bileşen) ──")
    train_rul(monitors)
    print("\n── 4) Tahminci LSTM (30 sn ileri) ──")
    for i, etype in enumerate(TYPE_EQ):
        train_forecaster(etype, seed=i)
    print("\nEğitim tamamlandı → ml/artifacts/")


if __name__ == "__main__":
    main()
