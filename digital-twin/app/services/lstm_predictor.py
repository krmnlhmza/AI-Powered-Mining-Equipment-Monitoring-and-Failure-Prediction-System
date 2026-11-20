"""
LSTM servisleri v2
══════════════════
1) predict(sequence)        — son 20 okuma → 30 sn sonrasının 5 sensör tahmini
2) predict_rul(equipment_id) — çalışma-saati özet dizisi → kalan faydalı ömür
                               (saat) + arızalanması beklenen bileşen olasılıkları

v1'deki sabit "_DEMO_RUL" tablosu ve fizik tavanıyla kırpma KALDIRILDI:
gösterilen RUL ve bileşen doğrudan modelin çıktısıdır. Bileşen
açıklamaları (arıza adı, sistem, gerekçe metni) yalnızca modelin seçtiği
sınıfın insan-okur açıklamasıdır.
"""

from __future__ import annotations

import os
import pickle
from typing import Dict, List, Optional

import numpy as np
import torch

ART = "ml/artifacts"
SEQ_LEN = 20                 # tahminci girdisi (okuma); API uyumluluğu için dışa açık
_rul = None
_fc: Dict[str, tuple] = {}


def _load_rul():
    global _rul
    if _rul is None:
        from ml.train import RULNet
        with open(f"{ART}/rul_meta.pkl", "rb") as f:
            meta = pickle.load(f)
        m = RULNet(meta["in_dim"])
        m.load_state_dict(torch.load(f"{ART}/rul_lstm.pt", map_location="cpu", weights_only=True))
        m.eval()
        _rul = (m, meta)
    return _rul


def _load_fc(eq_type: str):
    if eq_type not in _fc:
        from ml.train import ForecastNet
        with open(f"{ART}/forecast_{eq_type}_meta.pkl", "rb") as f:
            meta = pickle.load(f)
        m = ForecastNet(len(meta["features"]))
        m.load_state_dict(torch.load(f"{ART}/forecast_{eq_type}.pt", map_location="cpu",
                                     weights_only=True))
        m.eval()
        _fc[eq_type] = (m, meta)
    return _fc[eq_type]


# ─────────────────────────────────────────────────────────────────
# 1) Kısa vadeli tahmin
# ─────────────────────────────────────────────────────────────────
def predict(sequence: List[List[float]], equipment_id: Optional[str] = None) -> dict:
    """sequence: [[temp, vib, pres, cur, spd], ...] (≥ 20 okuma, ~3 sn aralık)."""
    from data.simulator import EQUIPMENT_PROFILES
    if len(sequence) < SEQ_LEN:
        return {"error": f"En az {SEQ_LEN} adım gerekli"}
    eq_type = EQUIPMENT_PROFILES.get(equipment_id or "", {}).get("type", "loader")
    m, meta = _load_fc(eq_type)
    x = np.asarray(sequence[-meta["seq"]:], np.float32)
    xn = (x - meta["mu"]) / meta["sd"]
    with torch.no_grad():
        d = m(torch.from_numpy(xn[None].astype(np.float32))).numpy()[0]
    pred = x[-1] + d * meta["sd"]
    out = {k: round(float(v), 3) for k, v in zip(meta["features"], pred)}
    out["ufuk_saniye"] = int(meta["horizon"] * meta["dt"])
    return out


# ─────────────────────────────────────────────────────────────────
# 2) Kalan faydalı ömür
# ─────────────────────────────────────────────────────────────────
def _rul_window(snaps: List[np.ndarray], is_truck: float, meta: dict) -> np.ndarray:
    w = np.array(snaps[-meta["seq"]:], np.float32)
    if len(w) < meta["seq"]:
        w = np.concatenate([np.repeat(w[:1], meta["seq"] - len(w), 0), w])
    w = np.concatenate([w, np.full((len(w), 1), is_truck, np.float32)], 1)
    return np.clip((w - meta["mu"]) / meta["sd"], -10, 10).astype(np.float32)


def rul_from_snapshots(snaps: List[np.ndarray], eq_type: str) -> dict:
    m, meta = _load_rul()
    x = _rul_window(snaps, float(eq_type == "truck"), meta)
    with torch.no_grad():
        r, logits = m(torch.from_numpy(x[None]))
    probs = torch.softmax(logits, -1).numpy()[0]
    return {"rul_saat": float(r.numpy()[0]) * meta["cap"], "probs": probs, "meta": meta}


def predict_rul(equipment_id: str, sequence=None) -> dict:
    """Canlı RUL: makinenin özet geçmişinden (anomaly_detector besler).
    `sequence` parametresi geriye dönük uyumluluk için kabul edilir, kullanılmaz."""
    from app.services.anomaly_detector import get_stream
    from data.simulator import COMPONENTS, EQUIPMENT_PROFILES
    from ml.features import TARGETS
    if equipment_id not in EQUIPMENT_PROFILES:
        return {"hata": f"Bilinmeyen ekipman: {equipment_id}"}
    _, meta = _load_rul()
    st = get_stream(equipment_id)
    snaps = st.snapshots
    if len(snaps) < meta["min_snaps"]:
        return {"hata": f"En az {meta['min_snaps']} çalışma-saati özeti gerekli "
                        f"(mevcut: {len(snaps)}; her özet {int(4)} çalışma saati)"}
    eq_type = EQUIPMENT_PROFILES[equipment_id]["type"]
    out = rul_from_snapshots(snaps, eq_type)
    return _rul_response(equipment_id, out, snaps[-1], COMPONENTS, TARGETS)


_SENSOR_AD = {"temperature": "Sıcaklık", "vibration": "Titreşim", "pressure": "Basınç",
              "current": "Akım", "fuel": "Yakıt"}


def _rul_response(equipment_id, out, last_snap, COMPONENTS, TARGETS) -> dict:
    meta = out["meta"]
    comps = meta["components"]
    probs = out["probs"]
    rul_h = round(out["rul_saat"], 1)
    cap = meta["cap"]
    healthy_p = float(probs[len(comps)])
    ci = int(np.argmax(probs[:len(comps)]))
    comp = comps[ci]
    info = COMPONENTS[comp]

    mean_z = last_snap[:len(TARGETS)]
    j = int(np.argmax(np.abs(mean_z)))
    baskin = _SENSOR_AD[TARGETS[j]]
    siddet = float(min(100.0, abs(mean_z[j]) / 8.0 * 100.0))

    if rul_h < 24:
        durum, renk = "KRİTİK", "kirmizi"
        oneri = "Acil bakım gerekli: ilgili bileşen en kısa sürede kontrol edilmeli/değiştirilmeli."
    elif rul_h < 72:
        durum, renk = "UYARI", "sari"
        oneri = "Planlı bakım penceresi öneriliyor; ilgili sistem yakından izlenmeli."
    else:
        durum, renk = "SAĞLIKLI", "yesil"
        oneri = "Belirgin bozulma yok; planlı bakım takvimi yeterli."
    yakin_ariza = durum != "SAĞLIKLI" and healthy_p < 0.5
    ufuk = f"≥{int(cap)}" if rul_h >= cap * 0.97 else None
    return {
        "equipment_id": equipment_id,
        "rul_saat": rul_h,
        "rul_gun": round(rul_h / 24, 1),
        "rul_ust_sinir": ufuk,
        "saglik_yuzde": round(min(100.0, rul_h / cap * 100.0), 1),
        "durum": durum,
        "renk": renk,
        "baskin_sensor": baskin,
        "sensor_doluluk": round(siddet, 1),
        "ariza": info["ad"] if yakin_ariza else None,
        "sistem": info["sistem"] if yakin_ariza else None,
        "gerekce": info["gerekce"] if yakin_ariza else
                   f"Sensör artıkları sağlıklı bantta (en büyük sapma: {baskin}).",
        "oneri": oneri,
        "bilesen_olasilik": {c: round(float(p), 3) for c, p in zip(comps, probs)}
                            | {"saglikli": round(healthy_p, 3)},
        "model": "LSTM (çalışma-saati özetleri)",
    }


def offline_degradation_demo(equipment_id: str, ilerleme: float = 0.7,
                             bilesen: Optional[str] = None, seed: Optional[int] = None) -> dict:
    """Çevrimdışı doğrulama senaryosu: canlıdan bağımsız, YENİ bir makinede
    bir bileşeni sondan sona bozar; ömrünün `ilerleme` noktasında modeli
    çalıştırır ve gerçek RUL ile birlikte döner (modelin dürüst sınaması)."""
    from app.services.anomaly_detector import _monitor
    from data.simulator import (COMPONENTS, COMPONENT_NAMES, EQUIPMENT_PROFILES, SENSORS,
                                FAULT_ALIASES, simulate_streams)
    from ml.features import TARGETS, residuals_batch, snapshots_batch
    prof = EQUIPMENT_PROFILES[equipment_id]
    rng = np.random.default_rng(seed)
    s = simulate_streams(equipment_id, 1, 4800, seed=int(rng.integers(1e9)), mode="run_to_failure",
                         manual_prob=0.0)
    comp = FAULT_ALIASES.get(bilesen, bilesen)
    if comp in COMPONENT_NAMES and COMPONENT_NAMES[int(s["true_comp"][0, 0])] != comp:
        # İstenen bileşen için tekrar üret (run_to_failure tek birimde bileşeni sırayla seçer)
        for k in range(1, 40):
            s = simulate_streams(equipment_id, 1, 4800, seed=int(rng.integers(1e9)),
                                 mode="run_to_failure", manual_prob=0.0)
            if COMPONENT_NAMES[int(s["true_comp"][0, 0])] == comp:
                break
    mon = _monitor(prof["type"])
    z, ctx = residuals_batch(mon["nbm"], s["X"], SENSORS, prof, s["interval_s"])
    snaps, ends = snapshots_batch(z, ctx, s["op_hours"], s["valid"])[0]
    k = int(np.clip(round(ilerleme * (len(snaps) - 1)), 3, len(snaps) - 1))
    out = rul_from_snapshots(list(snaps[:k + 1]), prof["type"])
    res = _rul_response(equipment_id, out, snaps[k], COMPONENTS, TARGETS)
    t = ends[k]
    res["gercek_rul"] = round(float(s["true_rul"][0, t]), 1)
    res["gercek_bilesen"] = COMPONENT_NAMES[int(s["true_comp"][0, t])]
    res["hasar_seviyesi"] = round(float(s["max_damage"][0, t]), 3)
    res["senaryo"] = f"çevrimdışı bozulma (ömrün %{int(ilerleme*100)} noktası)"
    return res
