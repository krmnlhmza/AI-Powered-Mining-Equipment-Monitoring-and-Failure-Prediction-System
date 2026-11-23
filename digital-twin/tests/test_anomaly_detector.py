"""Anomali tespiti v2: NBM artığı + Isolation Forest + kalıcılık kuralı."""

import pytest

from data.simulator import EQUIPMENT_PROFILES
from tests.conftest import okumalar, yeni_ikiz


@pytest.mark.parametrize("eq_id", ["LH517i_001", "TH551i_001"])
def test_saglikli_makinede_yanlis_alarm_yok(temiz_dedektor, eq_id):
    ad = temiz_dedektor
    tw = yeni_ikiz(eq_id, seed=21)
    sonuc = [ad.detect(r, eq_id) for r in okumalar(tw, 300)]
    assert not any(s["is_anomaly"] for s in sonuc)
    assert all(s["description"] is None for s in sonuc)
    assert all(0.0 <= s["anomaly_score"] <= 1.0 for s in sonuc)


@pytest.mark.parametrize("eq_id, bilesen", [
    ("LH517i_001", "rulman"),
    ("LH517i_001", "hidrolik_pompa"),
    ("TH551i_001", "motor_sargi"),
])
def test_baslatilan_ariza_yakalanir(temiz_dedektor, eq_id, bilesen):
    ad = temiz_dedektor
    tw = yeni_ikiz(eq_id, seed=31)
    for r in okumalar(tw, 120):                  # devreye alma (ilk 100 okuma = makinenin normali)
        assert not ad.detect(r, eq_id)["is_anomaly"]
    tw.start_fault(bilesen)
    for k, r in enumerate(okumalar(tw, 200, k0=120)):
        s = ad.detect(r, eq_id)
        if s["is_anomaly"]:
            assert s["anomaly_score"] >= ad.UYARI_ESIGI
            assert s["description"].startswith(f"Anomali ({eq_id})")
            return
    pytest.fail(f"{bilesen} arızası 200 okumada yakalanmadı")


def test_kalicilik_kurali_uc_ardisik_okuma(temiz_dedektor, monkeypatch):
    """Tek bir yüksek skor anomali sayılmaz; art arda ARDISIK_TEYIT okuma gerekir."""
    import numpy as np
    ad = temiz_dedektor
    eq = "LH517i_001"
    mon = ad._monitor(EQUIPMENT_PROFILES[eq]["type"])
    # IF ham skorunu kalibrasyon ekseninin en üstüne sabitle → skor = 1.0
    monkeypatch.setattr(mon["iforest"], "score_samples",
                        lambda X: np.full(len(X), -mon["calib"]["xp"][-1] * 2))
    tw = yeni_ikiz(eq, seed=41)
    kararlar = [ad.detect(r, eq)["is_anomaly"] for r in okumalar(tw, ad.ARDISIK_TEYIT + 1)]
    assert kararlar == [False] * (ad.ARDISIK_TEYIT - 1) + [True, True]


def test_kenar_tetikleme_olay_basina_tek_alarm(temiz_dedektor):
    ad = temiz_dedektor
    seri = [False, True, True, True, False, True]
    assert [ad.yeni_olay_mu("X", a) for a in seri] == [False, True, False, False, False, True]
