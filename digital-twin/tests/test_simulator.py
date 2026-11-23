"""Fizik tabanlı dijital ikiz (data/simulator.py)."""

import numpy as np
import pytest

from data import simulator as sim
from tests.conftest import okumalar, yeni_ikiz


@pytest.mark.parametrize("gaz, seviye", [
    (0.3, "NORMAL"), (1.0, "UYARI"), (1.6, "TEHLİKE"), (2.0, "KRİTİK"), (3.5, "KRİTİK"),
])
def test_gas_status_esikleri(gaz, seviye):
    assert sim.gas_status(gaz)["seviye"] == seviye


@pytest.mark.parametrize("eq_id", sim.EQUIPMENT_PROFILES)
def test_okuma_tum_sensorleri_tasir(eq_id):
    r = sim.generate_reading(eq_id)
    assert r["equipment_id"] == eq_id
    assert r["equipment_type"] == sim.EQUIPMENT_PROFILES[eq_id]["type"]
    for k in sim.SENSORS:
        assert np.isfinite(r[k]), k
    assert r["phase"] in sim.ALL_PHASES
    assert r["op_hours"] > 0
    assert 0.0 <= r["wear_level"] <= 1.0


def test_bilinmeyen_ekipman_ilk_profile_duser():
    r = sim.generate_reading("YOK_001")
    assert r["equipment_id"] == next(iter(sim.EQUIPMENT_PROFILES))


@pytest.mark.parametrize("eq_id", sim.EQUIPMENT_PROFILES)
def test_saglikli_akista_degerler_fiziksel(eq_id):
    """Sıcaklık ardışık okumalarda zıplamaz (ısıl zaman sabiti ~4 dk)."""
    tw = yeni_ikiz(eq_id, seed=11)
    rs = list(okumalar(tw, 200))
    temp = np.array([r["temperature"] for r in rs])
    assert np.abs(np.diff(temp)).max() < 3.0
    assert all(r["speed"] >= 0 and r["rpm"] >= 0 for r in rs)
    assert tw.D.max() == 0.0                     # doğal arıza kapalı → hasar yok


def test_ariza_buyur_ve_bakim_sifirlar():
    tw = yeni_ikiz("LH517i_001", seed=5)
    i = sim.COMPONENT_NAMES.index("rulman")
    tw.start_fault("rulman")
    d0 = tw.D[0, i]
    list(okumalar(tw, 20))
    assert tw.D[0, i] > d0                       # hasar kendini hızlandırarak büyür
    tw.repair(0, "rulman")
    assert tw.D[0, i] == 0.0


def test_gercek_rul_hasarla_azalir():
    tw = yeni_ikiz("TH551i_001", seed=6)
    tw.start_fault("hidrolik_pompa")
    rul1 = tw.true_rul()[0][0]
    list(okumalar(tw, 20))
    rul2 = tw.true_rul()[0][0]
    assert rul2 < rul1


def test_canli_ikiz_bakim_ve_durum():
    eq = "LH517i_002"
    comp = sim.start_fault(eq, "rulman")
    assert comp == "rulman"
    durum = sim.twin_status(eq)
    assert durum["hasar"]["rulman"] > 0
    assert durum["olaylar"][-1]["tip"] == "arıza_başlatıldı"
    assert "rulman" in sim.maintenance(eq, "rulman")["yenilenen"]
    assert sim.twin_status(eq)["hasar"]["rulman"] == 0.0


def test_manuel_faz_ve_otomatik_donus():
    eq = "TH551i_001"
    sim.set_manual_phase(eq, "climbing_loaded")
    assert sim._get_state(eq).manual_phase == "climbing_loaded"
    sim.set_manual_phase(eq, "auto")
    assert sim._get_state(eq).manual_phase is None
