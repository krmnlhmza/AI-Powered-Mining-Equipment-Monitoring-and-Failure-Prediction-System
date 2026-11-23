"""Ortak veri hattı (app/services/pipeline.py) — altyapısız (DB/Redis/MQTT sahte)."""

import asyncio
import json

import pytest

from app.models.sensor import AnomalyLog, SensorReading
from app.services import events, pipeline
from data.simulator import generate_reading


class SahteOturum:
    def __init__(self):
        self.eklenen, self.commit_sayisi, self._id = [], 0, 0

    def add(self, obj):
        self.eklenen.append(obj)

    async def commit(self):
        self.commit_sayisi += 1

    async def refresh(self, obj):
        if getattr(obj, "id", None) is None:
            self._id += 1
            obj.id = self._id

    async def close(self):
        pass


class SahteRedis:
    def __init__(self):
        self.veri = {}

    async def setex(self, key, ttl, value):
        self.veri[key] = json.loads(value)


@pytest.fixture
def hat(monkeypatch, temiz_dedektor):
    """Dış servisleri kaydedicilerle değiştirir; dedektör kararlarını sıraya koyar."""
    from app import redis_client
    from app.services import embedding_service, lstm_predictor, mailer, n8n_notifier

    cagri = {"notify": [], "store": [], "mail": [], "rul": []}
    sira = []   # detect'in döneceği (is_anomaly, skor) sırası

    def sahte_detect(reading, equipment_id=None):
        anom, skor = sira.pop(0)
        return {"is_anomaly": anom, "anomaly_score": skor,
                "description": f"Anomali ({reading['equipment_id']}): titreşim" if anom else None,
                "sapmalar": {"vibration": 6.0}, "skor_kaynagi": "isolation_forest"}

    def sahte_rul(eq_id, sequence=None):
        cagri["rul"].append(eq_id)
        return {"rul_saat": 42.0, "ariza": "Rulman aşınması", "sistem": "Aktarma",
                "durum": "KRİTİK", "baskin_sensor": "vibration"}

    monkeypatch.setattr(temiz_dedektor, "detect", sahte_detect)
    monkeypatch.setattr(lstm_predictor, "predict_rul", sahte_rul)
    monkeypatch.setattr(n8n_notifier, "notify", lambda p: cagri["notify"].append(p))
    monkeypatch.setattr(embedding_service, "store_anomaly",
                        lambda d, m: cagri["store"].append((d, m)))
    monkeypatch.setattr(mailer, "kritik_anomali_bildir", lambda *a: cagri["mail"].append(a))
    redis = SahteRedis()
    monkeypatch.setattr(redis_client, "redis_client", redis)
    # Arka plan işlerini eşzamanlı çalıştır (test deterministik olsun)
    monkeypatch.setattr(pipeline, "_background", lambda f, *a: f(*a))

    kuyruk = events.subscribe()
    yield {"sira": sira, "cagri": cagri, "redis": redis, "kuyruk": kuyruk}
    events.unsubscribe(kuyruk)


def _olaylar(kuyruk):
    out = []
    while not kuyruk.empty():
        out.append(kuyruk.get_nowait())
    return out


def _isle(reading, db):
    return asyncio.run(pipeline.process_reading(reading, db))


def test_normal_okuma_kaydedilir_ve_yayinlanir(hat):
    hat["sira"].append((False, 0.12))
    db = SahteOturum()
    r = generate_reading("LH517i_001")
    rec = _isle(r, db)

    assert isinstance(rec, SensorReading) and rec.id == 1
    assert rec.rpm == pytest.approx(r["rpm"]) and rec.fuel == pytest.approx(r["fuel"])
    assert not any(isinstance(o, AnomalyLog) for o in db.eklenen)
    assert db.commit_sayisi == 1

    son = hat["redis"].veri["latest:LH517i_001"]
    assert son["phase"] == r["phase"]                  # 3D ikiz faz bilgisini kullanır
    assert son["gas_status"]["seviye"] == "NORMAL"

    olaylar = _olaylar(hat["kuyruk"])
    assert [o["type"] for o in olaylar] == ["reading"]
    assert olaylar[0]["data"]["equipment_id"] == "LH517i_001"
    assert not hat["cagri"]["notify"] and not hat["cagri"]["rul"]


def test_yeni_anomali_olayi_tek_alarm_uretir(hat):
    hat["sira"].extend([(True, 0.65), (True, 0.66), (False, 0.2)])
    db = SahteOturum()
    for _ in range(3):
        _isle(generate_reading("TH551i_001"), db)

    alarmlar = [o for o in db.eklenen if isinstance(o, AnomalyLog)]
    assert len(alarmlar) == 1                          # episod boyunca tek kayıt
    assert "OTOMATİK TAHMİN" in alarmlar[0].description
    assert hat["cagri"]["rul"] == ["TH551i_001"]

    tipler = [o["type"] for o in _olaylar(hat["kuyruk"])]
    assert tipler == ["reading", "alarm", "reading", "reading"]

    (bildirim,) = hat["cagri"]["notify"]
    assert bildirim["rul_saat"] == 42.0 and bildirim["supheli_bilesen"] == "vibration"
    (gomulen, meta), = hat["cagri"]["store"]
    assert "OTOMATİK TAHMİN" not in gomulen            # benzerlik araması yalın açıklamayla
    assert meta["equipment_id"] == "TH551i_001"
    assert hat["cagri"]["mail"] == []                  # 0.65 < kritik eşik (0.7)


def test_kritik_skor_eposta_tetikler(hat):
    hat["sira"].append((True, 0.91))
    _isle(generate_reading("LH517i_002"), SahteOturum())
    (mail,) = hat["cagri"]["mail"]
    assert mail[0] == "LH517i_002" and mail[1] == 0.91


def test_redis_hatasi_hatti_durdurmaz(hat, monkeypatch):
    from app import redis_client

    class Bozuk:
        async def setex(self, *a):
            raise ConnectionError("redis yok")

    monkeypatch.setattr(redis_client, "redis_client", Bozuk())
    hat["sira"].append((False, 0.1))
    rec = _isle(generate_reading("LH517i_001"), SahteOturum())
    assert rec.id == 1
    assert [o["type"] for o in _olaylar(hat["kuyruk"])] == ["reading"]   # SSE yine çalışır


def test_olay_kuyrugu_doluysa_en_eskiyi_duser():
    q = events.subscribe()
    try:
        for i in range(q.maxsize + 5):
            events.publish({"type": "reading", "data": {"i": i}})
        assert q.qsize() == q.maxsize
        assert q.get_nowait()["data"]["i"] == 5
    finally:
        events.unsubscribe(q)
