"""
Model Değerlendirme v2 — dürüst karne
═════════════════════════════════════
Çalıştırma:  .venv/bin/python ml/evaluate.py

Kurallar:
  • Tüm test filoları eğitimde KULLANILMAMIŞ tohumlarla üretilen yeni
    makinelerdir (birim bazında ayrık).
  • Canlıdaki karar kuralı birebir uygulanır (yumuşatma + 3 ardışık teyit).
  • Her model basit bir referansla (baseline) kıyaslanır; LSTM'in katkısı
    ancak referansı geçtiği kadardır.
  • Sonuçlar ml/artifacts/evaluation.json'a yazılır.

Bölümler:
  0) Tutarlılık: canlı (okuma okuma) özellik kodu = toplu eğitim kodu
  1) Anomali: sağlıklı filoda yanlış alarm; bozulan filoda yakalama oranı,
     arızadan kaç çalışma saati önce yakalandığı (öncü süre)
  2) RUL: RMSE / MAE / NASA skoru; sabit tahmin ve gradyan artırma
     (zamansal olmayan) referanslarına karşı; bileşen sınıflandırma doğruluğu
  3) Tahminci: 30 sn ileri tahmin, "değişmez" (persistence) referansına karşı
"""

from __future__ import annotations

import json
import os
import pickle
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import numpy as np
import torch

from data.simulator import (COMPONENT_NAMES, EQUIPMENT_PROFILES, SENSORS,
                            simulate_streams)
from ml.features import TARGETS, StreamFeatures, residuals_batch, smooth_z_batch
from ml.train import (ART, DT, FC_FEATURES, FC_HORIZON, FC_SEQ, HEALTHY_CLASS,
                      RUL_CAP, TYPE_EQ, ForecastNet, RULNet, apply_calibration,
                      build_rul_dataset, forecast_windows)

EVAL_SEED = 9000          # eğitimde kullanılmayan tohum aralığı
ESIK, TEYIT = 0.6, 3
REPORT: dict = {}


def load_monitors():
    return {t: pickle.load(open(f"{ART}/monitor_{t}.pkl", "rb")) for t in TYPE_EQ}


def scores(mon, X, prof):
    z, ctx = residuals_batch(mon["nbm"], X, SENSORS, prof, DT)
    zs = smooth_z_batch(z, DT)
    flat = zs.reshape(-1, zs.shape[-1])
    s_if = apply_calibration(-mon["iforest"].score_samples(flat), mon["calib"])
    s_z = apply_calibration(np.abs(flat).max(1), mon["calib_z"])
    return np.maximum(s_if, s_z).reshape(zs.shape[:2]), z, ctx


def decisions(score):
    """Canlı kural: art arda TEYIT okuma ≥ ESIK → anomali."""
    run = np.zeros(score.shape[0])
    out = np.zeros(score.shape, bool)
    for t in range(score.shape[1]):
        run = np.where(score[:, t] >= ESIK, run + 1, 0)
        out[:, t] = run >= TEYIT
    return out


# ─────────────────────────────────────────────────────────────
def check_equivalence(monitors):
    print("0) Tutarlılık: canlı özellik kodu ↔ toplu eğitim kodu")
    eq = "LH517i_001"
    prof = EQUIPMENT_PROFILES[eq]
    s = simulate_streams(eq, 1, 600, seed=EVAL_SEED - 1, mode="healthy")
    _, z_b, _ = scores(monitors["loader"], s["X"], prof)
    sf = StreamFeatures(prof, monitors["loader"]["nbm"], SENSORS)
    z_l = []
    for t in range(s["X"].shape[1]):
        r = {k: float(s["X"][0, t, i]) for i, k in enumerate(SENSORS)}
        r["op_hours"] = float(s["op_hours"][0, t])
        z_l.append(sf.update(r, t * DT)["z"])
    d = float(np.abs(np.array(z_l) - z_b[0]).max())
    print(f"   en büyük fark |z_canlı − z_toplu| = {d:.2e}  → {'TAMAM' if d < 1e-3 else 'UYUMSUZ!'}\n")
    REPORT["tutarlilik_max_fark"] = d


# ─────────────────────────────────────────────────────────────
def eval_anomaly(monitors):
    print("1) ANOMALİ TESPİTİ (NBM artıkları + Isolation Forest + artık limiti)")
    REPORT["anomali"] = {}
    for k, (etype, eq) in enumerate(TYPE_EQ.items()):
        prof = EQUIPMENT_PROFILES[eq]
        mon = monitors[etype]
        h = simulate_streams(eq, 120, 3600, seed=EVAL_SEED + k, mode="healthy")
        sc, _, _ = scores(mon, h["X"], prof)
        dec = decisions(sc)
        episodes = int((dec[:, 1:] & ~dec[:, :-1]).sum() + dec[:, 0].sum())
        sim_hours = float((h["op_hours"][:, -1] - h["op_hours"][:, 0]).sum())
        real_hours = h["X"].shape[0] * h["X"].shape[1] * DT / 3600

        r = simulate_streams(eq, 240, 4800, seed=EVAL_SEED + 10 + k, mode="run_to_failure")
        sc_r, _, _ = scores(mon, r["X"], prof)
        dec_r = decisions(sc_r) & r["valid"]
        rows = []
        for u in range(r["X"].shape[0]):
            T = int(r["valid"][u].sum())
            failed = r["max_damage"][u, T - 1] >= 1.0
            if not failed:
                continue
            onset_idx = np.nonzero(r["max_damage"][u, :T] > 0)[0]
            pre = dec_r[u, :onset_idx[0]] if len(onset_idx) else dec_r[u, :T]
            hits = np.nonzero(dec_r[u, onset_idx[0] if len(onset_idx) else 0:T])[0]
            comp = COMPONENT_NAMES[int(r["true_comp"][u, T - 1])]
            if len(hits):
                t = hits[0] + (onset_idx[0] if len(onset_idx) else 0)
                rows.append((comp, True, float(r["true_rul"][u, t]), float(r["max_damage"][u, t]),
                             bool(pre.any())))
            else:
                rows.append((comp, False, 0.0, 1.0, bool(pre.any())))
        det = np.array([x[1] for x in rows])
        lead = np.array([x[2] for x in rows if x[1]])
        print(f"  [{etype}] sağlıklı filo: {real_hours:.0f} gerçek saat / {sim_hours:.0f} çalışma saati, "
              f"alarm olayı {episodes}  → {episodes / sim_hours * 1000:.2f} / 1000 çalışma saati;  "
              f"okumaların %{dec.mean()*100:.3f}'ü anomali")
        print(f"  [{etype}] bozulan filo: {len(rows)} arıza, arızadan ÖNCE yakalanan %{det.mean()*100:.1f}; "
              f"öncü süre medyan {np.median(lead):.0f} sa (p10 {np.percentile(lead,10):.0f}, "
              f"p90 {np.percentile(lead,90):.0f})")
        per = {}
        for c in COMPONENT_NAMES:
            sel = [x for x in rows if x[0] == c]
            if not sel:
                continue
            d = np.mean([x[1] for x in sel])
            ld = [x[2] for x in sel if x[1]]
            dm = [x[3] for x in sel if x[1]]
            per[c] = {"n": len(sel), "yakalama": round(float(d), 3),
                      "oncu_sure_medyan_sa": round(float(np.median(ld)), 1) if ld else None,
                      "tespitte_hasar_medyan": round(float(np.median(dm)), 2) if dm else None}
            print(f"      {c:15s} n={len(sel):3d}  yakalama %{d*100:5.1f}  öncü süre medyan "
                  f"{per[c]['oncu_sure_medyan_sa']} sa  tespitteki hasar {per[c]['tespitte_hasar_medyan']}")
        REPORT["anomali"][etype] = {
            "yanlis_alarm_olay_1000sa": round(episodes / sim_hours * 1000, 3),
            "yanlis_alarm_okuma_orani": float(dec.mean()),
            "yakalama_orani": float(det.mean()),
            "oncu_sure_medyan_sa": float(np.median(lead)),
            "bilesen": per,
        }
    print()


# ─────────────────────────────────────────────────────────────
def nasa_score(pred, true):
    d = pred - true
    return float(np.sum(np.where(d < 0, np.exp(-d / 13) - 1, np.exp(d / 10) - 1)))


def eval_rul(monitors):
    print("2) KALAN FAYDALI ÖMÜR (RUL)")
    meta = pickle.load(open(f"{ART}/rul_meta.pkl", "rb"))
    m = RULNet(meta["in_dim"])
    m.load_state_dict(torch.load(f"{ART}/rul_lstm.pt", weights_only=True))
    m.eval()
    t0 = time.time()
    X, yr, yc, uid = build_rul_dataset(monitors, n_units=200, seed=EVAL_SEED + 100)
    Xn = np.clip((X - meta["mu"]) / meta["sd"], -10, 10).astype(np.float32)
    with torch.no_grad():
        pr, pc = [], []
        for i in range(0, len(Xn), 4096):
            a, b = m(torch.from_numpy(Xn[i:i + 4096]))
            pr.append(a.numpy()); pc.append(b.argmax(1).numpy())
    pred = np.concatenate(pr) * RUL_CAP
    pcls = np.concatenate(pc)
    true = yr * RUL_CAP

    # Referans 1: sabit (test etiketlerinin ortalaması — referans için iyimser)
    const = np.full_like(true, true.mean())
    # Referans 2: zamansal olmayan model — yalnız SON özet (eğitim filosunda eğitilir)
    from sklearn.ensemble import HistGradientBoostingRegressor
    Xtr, ytr, _, _ = build_rul_dataset(monitors, n_units=200, seed=EVAL_SEED + 300)
    gb = HistGradientBoostingRegressor(max_iter=300, random_state=0).fit(Xtr[:, -1], ytr * RUL_CAP)
    gbp = np.clip(gb.predict(X[:, -1]), 0, RUL_CAP)

    def row(name, p, mask):
        e = p[mask] - true[mask]
        return {"model": name, "RMSE": float(np.sqrt((e ** 2).mean())), "MAE": float(np.abs(e).mean()),
                "NASA": nasa_score(p[mask], true[mask]) / mask.sum()}

    REPORT["rul"] = {"pencere": int(len(true)), "birim": int(len(np.unique(uid)))}
    for label, mask in (("tüm pencereler", np.ones_like(true, bool)),
                        ("gerçek RUL ≤ 100 sa", true <= 100),
                        ("gerçek RUL ≤ 30 sa", true <= 30)):
        print(f"  {label}  (n={int(mask.sum())})")
        res = [row("sabit ortalama", const, mask), row("GBM (son özet)", gbp, mask),
               row("LSTM (özet dizisi)", pred, mask)]
        for r_ in res:
            print(f"     {r_['model']:20s} RMSE {r_['RMSE']:6.2f}  MAE {r_['MAE']:6.2f}  "
                  f"NASA/pencere {r_['NASA']:8.3f}")
        REPORT["rul"][label] = res

    near = yc != HEALTHY_CLASS
    acc = float((pcls[near] == yc[near]).mean())
    acc72 = float((pcls[true < 72] == yc[true < 72]).mean())
    print(f"  bileşen doğruluğu: RUL<{int(RUL_CAP)} pencerelerde %{acc*100:.1f}, RUL<72 sa pencerelerde %{acc72*100:.1f}")
    from collections import Counter
    conf = Counter((COMPONENT_NAMES[a], COMPONENT_NAMES[b] if b < len(COMPONENT_NAMES) else "saglikli")
                   for a, b in zip(yc[true < 72], pcls[true < 72]) if a != b)
    print("  en sık karışan çiftler (gerçek → tahmin):",
          ", ".join(f"{a}→{b} ({n})" for (a, b), n in conf.most_common(4)))
    REPORT["rul"]["bilesen_dogrulugu"] = acc
    REPORT["rul"]["bilesen_dogrulugu_rul72"] = acc72
    REPORT["rul"]["karisan_ciftler"] = [[a, b, n] for (a, b), n in conf.most_common(6)]
    print(f"  ({time.time()-t0:.0f} sn)\n")


# ─────────────────────────────────────────────────────────────
def eval_forecast():
    print(f"3) KISA VADELİ TAHMİN (son {FC_SEQ} okuma → {int(FC_HORIZON*DT)} sn sonrası)")
    REPORT["tahmin"] = {}
    for k, (etype, eq) in enumerate(TYPE_EQ.items()):
        meta = pickle.load(open(f"{ART}/forecast_{etype}_meta.pkl", "rb"))
        m = ForecastNet(len(FC_FEATURES))
        m.load_state_dict(torch.load(f"{ART}/forecast_{etype}.pt", weights_only=True))
        m.eval()
        s = simulate_streams(eq, 60, 1800, seed=EVAL_SEED + 400 + k, mode="healthy")
        X, Y = forecast_windows(s["X"], None, stride=5)
        with torch.no_grad():
            d = m(torch.from_numpy(((X - meta["mu"]) / meta["sd"]).astype(np.float32))).numpy()
        P = X[:, -1] + d * meta["sd"]
        lstm = np.abs(P - Y).mean(0)
        naive = np.abs(X[:, -1] - Y).mean(0)
        print(f"  [{etype}] {'sensör':12s} {'LSTM MAE':>9s} {'değişmez':>9s} {'iyileşme':>9s}")
        res = {}
        for i, f in enumerate(FC_FEATURES):
            imp = (1 - lstm[i] / naive[i]) * 100
            res[f] = {"lstm_mae": float(lstm[i]), "naif_mae": float(naive[i]), "iyilesme_yuzde": float(imp)}
            print(f"           {f:12s} {lstm[i]:9.3f} {naive[i]:9.3f} {imp:+8.0f}%")
        REPORT["tahmin"][etype] = res
    print()


if __name__ == "__main__":
    torch.set_num_threads(max(1, (os.cpu_count() or 2) // 2))
    mons = load_monitors()
    check_equivalence(mons)
    eval_anomaly(mons)
    eval_rul(mons)
    eval_forecast()
    with open(f"{ART}/evaluation.json", "w", encoding="utf-8") as f:
        json.dump(REPORT, f, ensure_ascii=False, indent=2)
    print("Karne → ml/artifacts/evaluation.json")
