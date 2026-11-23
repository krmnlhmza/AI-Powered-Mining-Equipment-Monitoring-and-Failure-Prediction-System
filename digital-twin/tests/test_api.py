"""Altyapı servisi (DB, Redis, MQTT, Qdrant) gerektirmeyen uç nokta testleri.

TestClient `with` olmadan kullanılır → uygulamanın açılış adımları
(bağlantılar, model ön yükleme) çalışmaz."""

import pytest
from fastapi.testclient import TestClient

import main

client = TestClient(main.app)

GECERLI = {"equipment_id": "LH517i_001", "equipment_type": "loader",
           "temperature": 80, "vibration": 2.1, "pressure": 265, "current": 170, "speed": 4}


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_kok_panele_yonlendirir():
    res = client.get("/", follow_redirects=False)
    assert res.status_code in (302, 307)
    assert res.headers["location"] == "/static/demo.html"


def test_panel_canli_akisa_baglanir():
    html = client.get("/static/demo.html").text
    assert "/dashboard/stream" in html and "EventSource" in html


def test_okuma_dogrulamasi():
    eksik = {k: v for k, v in GECERLI.items() if k != "temperature"}
    assert client.post("/sensors/reading", json=eksik).status_code == 422


@pytest.mark.parametrize("istek", [
    lambda: client.post("/sensors/reading", json={**GECERLI, "equipment_id": "YOK_001"}),
    lambda: client.post("/sensors/simulate/YOK_001"),
])
def test_bilinmeyen_ekipman_404(istek):
    assert istek().status_code == 404


def test_yeni_uc_noktalar_kayitli():
    yollar = client.get("/openapi.json").json()["paths"]
    assert "get" in yollar["/dashboard/stream"]
    assert "post" in yollar["/anomalies/resolve-all"]
