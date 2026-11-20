"""
Ortak özellik katmanı — eğitim ve canlı servis AYNI kodu kullanır
════════════════════════════════════════════════════════════════

Mimari (rüzgâr türbini SCADA izlemede yaygın "Normal Behaviour Model" yaklaşımı):

  ham okuma ──► çalışma bağlamı (devir, tork, hız + bunların zaman-EWMA'ları)
            └─► NORMAL DAVRANIŞ MODELİ (NBM): "bu koşulda sağlıklı makine
                sıcaklık/titreşim/basınç/akım/yakıt için ne ölçerdi?"
            └─► artık  z = (ölçülen − beklenen) / σ_sağlıklı

Neden? Ham değerler çalışma koşuluna boğulur: yokuşta yüksek sıcaklık
normaldir, rölantide değildir. Artık (z) ise koşuldan arındırılmış sağlık
sinyalidir. İki model bunun üzerine kurulur:
  • Isolation Forest → z'nin anlık (kısa EWMA) vektörü üzerinde anomali
  • RUL LSTM        → z'nin çalışma-saati pencerelerindeki özetleri (snapshot)

`StreamFeatures` canlıda okuma okuma çalışır; `stream_features_batch` aynı
özyinelemeyi eğitim için vektörel uygular. İkisinin eşdeğerliği testle
doğrulanır (ml/evaluate.py → kontrol).
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional

import numpy as np

TARGETS = ["temperature", "vibration", "pressure", "current", "fuel"]
CTX_RAW = ["rpm", "torque", "speed"]
CTX_TAUS = (60.0, 240.0)          # s — kısa ve ısıl zaman sabitli EWMA'lar
Z_TAU = 9.0                        # s — anomali için artık yumuşatma (~3 okuma)
SNAP_HOURS = 4.0                   # RUL özet penceresi (çalışma saati)
BASELINE_READINGS = 100            # devreye alma: makinenin kendi normali (~5 dk)
SNAP_MIN_READINGS = 3
N_CTX = len(CTX_RAW) * (1 + len(CTX_TAUS))
SNAP_DIM = 2 * len(TARGETS) + len(CTX_RAW)


def _norm_ctx(raw: np.ndarray, prof: dict) -> np.ndarray:
    """rpm/tork/hızı profil bandına göre 0-1'e ölçekle (tipler arası taşınabilir)."""
    out = np.empty_like(raw, dtype=float)
    for j, k in enumerate(CTX_RAW):
        lo, hi = prof[k]
        lo = 0.0 if k in ("torque", "speed") else lo
        out[..., j] = (raw[..., j] - lo) / (hi - lo)
    return out


# ─────────────────────────────────────────────────────────────────
# Normal davranış modeli
# ─────────────────────────────────────────────────────────────────
class NormalBehaviourModel:
    """Hedef başına HistGradientBoosting regresörü; artık ölçeği sağlam
    (MAD) tahminle, modelin görmediği sağlıklı veriden kalibre edilir."""

    def __init__(self):
        self.models = {}
        self.sigma = np.ones(len(TARGETS))

    def fit(self, ctx: np.ndarray, Y: np.ndarray, ctx_cal: np.ndarray, Y_cal: np.ndarray):
        from sklearn.ensemble import HistGradientBoostingRegressor
        for j, k in enumerate(TARGETS):
            m = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.08,
                                              max_leaf_nodes=31, random_state=0)
            m.fit(ctx, Y[:, j])
            self.models[k] = m
        res = Y_cal - self.predict(ctx_cal)
        mad = np.median(np.abs(res - np.median(res, axis=0)), axis=0)
        self.sigma = np.maximum(1.4826 * mad, 1e-6)
        return self

    def predict(self, ctx: np.ndarray) -> np.ndarray:
        return np.stack([self.models[k].predict(ctx) for k in TARGETS], axis=-1)

    def z(self, ctx: np.ndarray, Y: np.ndarray) -> np.ndarray:
        return (Y - self.predict(ctx)) / self.sigma


# ─────────────────────────────────────────────────────────────────
# Toplu (eğitim) özellik çıkarımı — [n, T, S] akışlardan
# ─────────────────────────────────────────────────────────────────
def stream_context_batch(X: np.ndarray, sensors: List[str], prof: dict,
                         dt: float) -> np.ndarray:
    """[n,T,S] → bağlam [n,T,N_CTX]. Canlıdaki StreamFeatures ile aynı özyineleme."""
    raw = np.stack([X[..., sensors.index(k)] for k in CTX_RAW], axis=-1)
    cn = _norm_ctx(raw, prof)
    n, T, _ = cn.shape
    parts = [cn]
    for tau in CTX_TAUS:
        a = 1.0 - math.exp(-dt / tau)
        e = np.empty_like(cn)
        e[:, 0] = cn[:, 0]
        for t in range(1, T):
            e[:, t] = e[:, t - 1] + a * (cn[:, t] - e[:, t - 1])
        parts.append(e)
    return np.concatenate(parts, axis=-1)


def targets_batch(X: np.ndarray, sensors: List[str]) -> np.ndarray:
    return np.stack([X[..., sensors.index(k)] for k in TARGETS], axis=-1)


def baseline_correct_batch(z: np.ndarray) -> np.ndarray:
    """Devreye alma kalibrasyonu: her makinenin ilk BASELINE_READINGS
    okumasındaki ortalama artık (o makinenin kendi sabit sapması) çıkarılır,
    sonra dondurulur. Devreye alma sırasında o ana kadarki ortalama kullanılır.
    Canlıdaki StreamFeatures ile birebir aynı."""
    n, T, k = z.shape
    N = min(BASELINE_READINGS, T)
    cs = np.cumsum(z[:, :N], axis=1) / np.arange(1, N + 1)[None, :, None]
    off = np.concatenate([cs, np.repeat(cs[:, -1:], T - N, axis=1)], axis=1)
    return z - off


def residuals_batch(nbm: "NormalBehaviourModel", X: np.ndarray, sensors: List[str],
                    prof: dict, dt: float):
    """[n,T,S] akış → (devreye alma düzeltmeli z [n,T,5], bağlam [n,T,N_CTX])."""
    ctx = stream_context_batch(X, sensors, prof, dt)
    Y = targets_batch(X, sensors)
    z = nbm.z(ctx.reshape(-1, N_CTX), Y.reshape(-1, len(TARGETS))).reshape(Y.shape)
    return baseline_correct_batch(z), ctx


def smooth_z_batch(z: np.ndarray, dt: float) -> np.ndarray:
    a = 1.0 - math.exp(-dt / Z_TAU)
    out = np.empty_like(z)
    out[:, 0] = z[:, 0]
    for t in range(1, z.shape[1]):
        out[:, t] = out[:, t - 1] + a * (z[:, t] - out[:, t - 1])
    return out


def snapshots_batch(z: np.ndarray, cn: np.ndarray, op_hours: np.ndarray,
                    valid: Optional[np.ndarray] = None):
    """Birim başına çalışma-saati pencereleri → özet dizisi.
    Dönüş: list (birim başına) of (snap [K, SNAP_DIM], end_index [K])."""
    out = []
    n = z.shape[0]
    for u in range(n):
        agg = SnapshotAggregator()
        snaps, ends = [], []
        T = z.shape[1] if valid is None else int(valid[u].sum())
        for t in range(T):
            s = agg.add(z[u, t], cn[u, t], float(op_hours[u, t]))
            if s is not None:
                snaps.append(s)
                ends.append(t)
        out.append((np.array(snaps, np.float32).reshape(-1, SNAP_DIM), np.array(ends, int)))
    return out


# ─────────────────────────────────────────────────────────────────
# Canlı (okuma okuma) özellik durumu
# ─────────────────────────────────────────────────────────────────
class SnapshotAggregator:
    """Artıkları SNAP_HOURS'lık çalışma saati pencerelerinde özetler:
    [ortalama z (5), std z (5), ortalama bağlam (rpm, tork, hız)]."""

    def __init__(self):
        self.start_h: Optional[float] = None
        self.z: List[np.ndarray] = []
        self.c: List[np.ndarray] = []

    def add(self, z: np.ndarray, cn_now: np.ndarray, op_hours: float) -> Optional[np.ndarray]:
        if self.start_h is None:
            self.start_h = op_hours
        self.z.append(np.asarray(z, float))
        self.c.append(np.asarray(cn_now[:len(CTX_RAW)], float))
        if op_hours - self.start_h >= SNAP_HOURS and len(self.z) >= SNAP_MIN_READINGS:
            Z, Cc = np.array(self.z), np.array(self.c)
            snap = np.concatenate([Z.mean(0), Z.std(0), Cc.mean(0)]).astype(np.float32)
            self.start_h, self.z, self.c = op_hours, [], []
            return snap
        return None


class StreamFeatures:
    """Tek makinenin canlı özellik durumu (EWMA bağlam, yumuşatılmış z, özetler)."""

    def __init__(self, prof: dict, nbm: NormalBehaviourModel, sensors: List[str]):
        self.prof, self.nbm, self.sensors = prof, nbm, sensors
        self.ew: Optional[np.ndarray] = None
        self.zs: Optional[np.ndarray] = None
        self.last_t: Optional[float] = None
        self.snap = SnapshotAggregator()
        self.snapshots: List[np.ndarray] = []
        self.readings_since_snap = 0
        self.base_sum = np.zeros(len(TARGETS))
        self.base_n = 0

    def update(self, reading: Dict[str, float], t_seconds: float) -> dict:
        raw = np.array([[float(reading[k]) for k in CTX_RAW]])
        cn = _norm_ctx(raw, self.prof)[0]
        dt = 3.0 if self.last_t is None else max(0.2, min(t_seconds - self.last_t, 60.0))
        self.last_t = t_seconds
        if self.ew is None:
            self.ew = np.concatenate([cn] * len(CTX_TAUS))
        else:
            for i, tau in enumerate(CTX_TAUS):
                a = 1.0 - math.exp(-dt / tau)
                sl = slice(i * len(CTX_RAW), (i + 1) * len(CTX_RAW))
                self.ew[sl] = self.ew[sl] + a * (cn - self.ew[sl])
        ctx = np.concatenate([cn, self.ew])[None, :]
        y = np.array([[float(reading[k]) for k in TARGETS]])
        expected = self.nbm.predict(ctx)[0]
        z = (y[0] - expected) / self.nbm.sigma
        if self.base_n < BASELINE_READINGS:          # devreye alma
            self.base_sum += z
            self.base_n += 1
        z = z - self.base_sum / self.base_n
        a = 1.0 - math.exp(-dt / Z_TAU)
        self.zs = z.copy() if self.zs is None else self.zs + a * (z - self.zs)
        op_h = reading.get("op_hours")
        if op_h is None:          # saat sayacı yoksa okuma sayısıyla pencerele
            self.readings_since_snap += 1
            op_h = self.readings_since_snap * SNAP_HOURS / 8.0
        s = self.snap.add(z, cn, float(op_h))
        if s is not None:
            self.snapshots.append(s)
            del self.snapshots[:-200]
        return {"z": z, "z_smooth": self.zs.copy(),
                "expected": expected + self.base_sum / self.base_n * self.nbm.sigma,
                "ctx": ctx[0], "devreye_alma": self.base_n < BASELINE_READINGS}
