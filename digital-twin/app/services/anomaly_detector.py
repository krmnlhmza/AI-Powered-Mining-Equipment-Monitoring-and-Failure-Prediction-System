"""
Anomali Tespiti v2 — Normal Davranış Modeli artıkları + Isolation Forest
═══════════════════════════════════════════════════════════════════════

Akış (her okuma için):
  1) Çalışma bağlamı (devir, tork, hız ve EWMA'ları) → NBM "sağlıklı makine
     burada ne ölçerdi?" → artık z = (ölçülen − beklenen) / σ
  2) z kısa süre yumuşatılır (~3 okuma) → iki dedektör, aynı kalibrasyonla:
       • Isolation Forest — çok-sensörlü örüntü sapması
       • Artık kontrol limiti max|z| — tek sensörde büyük sapma (IF'in doyduğu
         durum: ör. soğutma arızasında yalnız sıcaklık yükselir)
     skor = ikisinin büyüğü; 0.10 ≈ tipik sağlıklı, 0.50 = sağlıklının %99'u,
     0.60 = sağlıklı okumaların binde biri
  3) Kalıcılık kuralı: art arda 3 okuma ≥ 0.6 → anomali ilan edilir
  4) Kenar tetikleme: alarm yalnız normal→anomali geçişinde bir kez

v1'deki "enjekte arıza varsa sonucu zorla anomali yap" kısayolu KALDIRILDI.
Karar tamamen modele aittir; Canlı Test'te başlatılan arıza da ancak
sensörlere fiziksel olarak yansıdığında yakalanır.

Ayrıca her okuma, RUL modelinin kullandığı çalışma-saati özetlerini
(snapshot) besler: `get_stream(eq_id).snapshots`.
"""

from __future__ import annotations

import os
import pickle
import time
from datetime import datetime
from typing import Dict, Optional

import numpy as np

UYARI_ESIGI = 0.6
KRITIK_ESIGI = 0.7
ARDISIK_TEYIT = 3
ART = "ml/artifacts"

_monitors: Dict[str, dict] = {}
_streams: Dict[str, "object"] = {}
_ardisik: Dict[str, int] = {}
_anom_prev: Dict[str, bool] = {}

_LABELS = {"temperature": ("Sıcaklık", "°C"), "vibration": ("Titreşim", "mm/s"),
           "pressure": ("Basınç", "bar"), "current": ("Akım", "A"),
           "fuel": ("Yakıt", "L/sa")}


def _monitor(eq_type: str) -> dict:
    if eq_type not in _monitors:
        path = f"{ART}/monitor_{eq_type}.pkl"
        if not os.path.exists(path):
            raise FileNotFoundError(f"{path} yok — önce: .venv/bin/python ml/train.py")
        with open(path, "rb") as f:
            _monitors[eq_type] = pickle.load(f)
    return _monitors[eq_type]


def _load() -> None:
    """Açılışta tüm tip modellerini yükle."""
    from data.simulator import EQUIPMENT_PROFILES
    for p in EQUIPMENT_PROFILES.values():
        _monitor(p["type"])


def get_stream(equipment_id: str):
    from data.simulator import EQUIPMENT_PROFILES, SENSORS
    from ml.features import StreamFeatures
    if equipment_id not in _streams:
        prof = EQUIPMENT_PROFILES[equipment_id]
        _streams[equipment_id] = StreamFeatures(prof, _monitor(prof["type"])["nbm"], SENSORS)
    return _streams[equipment_id]


def _t_seconds(reading: Dict) -> float:
    t = reading.get("time")
    if isinstance(t, datetime):
        return t.timestamp()
    if hasattr(t, "timestamp"):
        return float(t.timestamp())
    return time.time()


def yeni_olay_mu(eq_id: str, is_anomaly: bool) -> bool:
    onceki = _anom_prev.get(eq_id, False)
    _anom_prev[eq_id] = is_anomaly
    return is_anomaly and not onceki


def detect(reading: Dict, equipment_id: Optional[str] = None) -> Dict:
    """Dönüş: {is_anomaly, anomaly_score, description, sapmalar}"""
    from data.simulator import EQUIPMENT_PROFILES
    eq_id = equipment_id or reading.get("equipment_id")
    if eq_id not in EQUIPMENT_PROFILES:
        eq_id = next(iter(EQUIPMENT_PROFILES))
    mon = _monitor(EQUIPMENT_PROFILES[eq_id]["type"])
    f = get_stream(eq_id).update(reading, _t_seconds(reading))

    raw = -float(mon["iforest"].score_samples(f["z_smooth"][None, :])[0])
    c, cz = mon["calib"], mon["calib_z"]
    s_if = float(np.clip(np.interp(raw, c["xp"], c["fp"]), 0.0, 1.0))
    s_z = float(np.clip(np.interp(float(np.abs(f["z_smooth"]).max()), cz["xp"], cz["fp"]), 0.0, 1.0))
    score = max(s_if, s_z)

    _ardisik[eq_id] = _ardisik.get(eq_id, 0) + 1 if score >= UYARI_ESIGI else 0
    is_anomaly = _ardisik[eq_id] >= ARDISIK_TEYIT

    from ml.features import TARGETS
    sapmalar = {k: round(float(z), 2) for k, z in zip(TARGETS, f["z_smooth"])}
    return {
        "is_anomaly": bool(is_anomaly),
        "anomaly_score": round(score, 4),
        "description": _describe(reading, f, score, eq_id) if is_anomaly else None,
        "sapmalar": sapmalar,
        "skor_kaynagi": "isolation_forest" if s_if >= s_z else "artik_limiti",
    }


def _describe(r: Dict, f: dict, score: float, eq_id: str) -> str:
    """En çok sapan sensörleri, beklenen değerle karşılaştırarak anlatır."""
    from ml.features import TARGETS
    zs = f["z_smooth"]
    order = np.argsort(-np.abs(zs))
    parts = []
    for j in order[:3]:
        if abs(zs[j]) < 4:
            continue
        k = TARGETS[j]
        ad, birim = _LABELS[k]
        yon = "yüksek" if zs[j] > 0 else "düşük"
        parts.append(f"{ad} beklenenden {yon} ({float(r[k]):.1f} {birim}, "
                     f"bu koşulda beklenen ≈{float(f['expected'][j]):.1f}; {zs[j]:+.1f}σ)")
    if not parts:
        parts.append("çoklu sensör örüntüsü sağlıklı davranıştan sapıyor")
    return f"Anomali ({eq_id}): " + "; ".join(parts) + f" — skor {score:.3f}"
