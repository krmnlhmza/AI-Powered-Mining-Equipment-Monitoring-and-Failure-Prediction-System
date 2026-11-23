import os
import sys

# Tek okumalık HistGradientBoosting tahmininde OpenMP iş parçacığı yükü baskın:
# tek iş parçacığı ~7 kat hızlı (okuma başına ~7 ms ↔ ~46 ms). OpenMP
# başlamadan ayarlanmalı.
os.environ.setdefault("OMP_NUM_THREADS", "1")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)   # model (ml/artifacts) ve statik dosya yolları depo köküne göredir

from datetime import datetime, timedelta, timezone  # noqa: E402

import pytest  # noqa: E402

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def yeni_ikiz(equipment_id: str, seed: int):
    """Doğal arızası kapalı, ısıl dengeye oturmuş yeni bir sanal makine."""
    from data.simulator import Fleet
    tw = Fleet(equipment_id, n=1, seed=seed, natural_faults=False)
    acc, tw.accel = tw.accel, 0.0
    for _ in range(600):
        tw.step(1.0)
    tw.accel = acc
    return tw


def okumalar(tw, n: int, k0: int = 0, aralik_s: float = 3.0):
    """Canlı akışla aynı aralıkta (3 sn) n okuma üretir."""
    from data.simulator import _package
    for k in range(n):
        for _ in range(int(aralik_s)):
            tw.step(1.0)
        r = _package(tw, tw.read())
        r["time"] = T0 + timedelta(seconds=aralik_s * (k0 + k))
        yield r


@pytest.fixture
def temiz_dedektor():
    """Dedektörün makine başına akış durumunu test öncesi/sonrası sıfırlar."""
    from app.services import anomaly_detector as ad

    def sifirla():
        ad._streams.clear()
        ad._ardisik.clear()
        ad._anom_prev.clear()

    sifirla()
    yield ad
    sifirla()
