"""
MQTT Sensör Abonesi (Subscriber)
---------------------------------
Backend'in veri giriş katmanı. Mosquitto broker'a abone olur, `maden/+/sensor`
topic'lerinden gelen her sensör mesajını alır ve işler:

    MQTT mesajı → anomali tespiti (Isolation Forest)
                → TimescaleDB'ye kayıt
                → Redis'e son durum (canlı dashboard)
                → anomali ise: AnomalyLog + n8n alarmı + Qdrant'a embedding

paho-mqtt kendi thread'inde (loop_start) çalışır. Gelen her mesaj,
asyncio.run_coroutine_threadsafe ile FastAPI'nin ana event loop'una aktarılır.
Böylece async DB/Redis işlemleri güvenle yürütülür.
"""

import os
import json
import asyncio
import paho.mqtt.client as mqtt

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
TOPIC = "maden/+/sensor"

_client: mqtt.Client = None
_loop: asyncio.AbstractEventLoop = None


async def otomatik_tahmin(db, eq_id: str, guncel: list = None) -> tuple:
    """OTOMATİK ARIZA TAHMİNİ (anomali → RUL zinciri) — paylaşılan yardımcı.

    Anomali yakalanınca RUL LSTM'e sorulur: "hangi bileşen bozuluyor, ne kadar
    ömür kaldı?" Hem MQTT yolu hem HTTP yolu bu TEK fonksiyonu kullanır.
    Dönüş: (uyarı metnine eklenecek cümle, ham tahmin dict'i)"""
    from app.services.lstm_predictor import predict_rul
    try:
        rul = await asyncio.get_event_loop().run_in_executor(None, predict_rul, eq_id)
        if "rul_saat" not in rul:
            return "", {}
        if rul.get("ariza"):
            metin = (f" || OTOMATİK TAHMİN → Olası arıza: {rul['ariza']} "
                     f"({rul['sistem']}); tahmini kalan ömür ~{rul['rul_saat']:.0f} saat "
                     f"({rul['durum']}).")
        else:
            metin = (f" || OTOMATİK TAHMİN → Kalıcı bozulma trendi henüz görülmüyor "
                     f"(RUL ~{rul['rul_saat']:.0f} saat); en büyük sapma: "
                     f"{rul['baskin_sensor']}. Kısa süreli sapma olabilir, izlenmeli.")
        return metin, rul
    except Exception as e:
        print(f"  otomatik RUL tahmini yapılamadı: {e}")
        return "", {}


async def _handle_reading(reading: dict):
    """Tek bir sensör okumasını işler (ana event loop'ta çalışır)."""
    from datetime import datetime, timezone
    from app.database import AsyncSessionLocal
    from app.models.sensor import SensorReading, AnomalyLog
    from app.services.anomaly_detector import detect as detect_anomaly, yeni_olay_mu
    from app.services.n8n_notifier import notify
    from app.services.embedding_service import store_anomaly
    from app.redis_client import redis_client
    from data.simulator import gas_status

    eq_id = reading.get("equipment_id", "unknown")
    result = detect_anomaly(reading)
    # Tek olay = tek alarm: episod boyunca yalnız ilk anomali okumasında tetikle
    yeni_olay = yeni_olay_mu(eq_id, result["is_anomaly"])

    # Metan (İSG) değerlendirmesi — mutlak eşik, ML'den bağımsız
    gas_val = float(reading.get("gas", 0.0))
    gas_eval = gas_status(gas_val)
    gas_alarm = gas_eval["seviye"] != "NORMAL"

    async with AsyncSessionLocal() as db:
        db.add(SensorReading(
            equipment_id   = eq_id,
            equipment_type = reading.get("equipment_type"),
            temperature    = reading["temperature"],
            vibration      = reading["vibration"],
            pressure       = reading["pressure"],
            current        = reading["current"],
            speed          = reading["speed"],
            gas            = gas_val,
            rpm            = reading.get("rpm"),
            torque         = reading.get("torque"),
            fuel           = reading.get("fuel"),
            is_anomaly     = result["is_anomaly"],
            anomaly_score  = result["anomaly_score"],
        ))

        if yeni_olay:
            tahmin_metni, rul_tahmin = await otomatik_tahmin(
                db, eq_id,
                [reading["temperature"], reading["vibration"], reading["pressure"],
                 reading["current"], reading["speed"]])

            db.add(AnomalyLog(
                equipment_id   = eq_id,
                equipment_type = reading.get("equipment_type"),
                anomaly_score  = result["anomaly_score"],
                description    = (result["description"] or "") + tahmin_metni,
            ))

            payload = {
                "equipment_id":  eq_id,
                "anomaly_score": result["anomaly_score"],
                "description":   (result["description"] or "") + tahmin_metni,
                "rul_saat":      rul_tahmin.get("rul_saat"),
                "supheli_bilesen": rul_tahmin.get("baskin_sensor"),
                "temperature":   reading["temperature"],
                "time":          datetime.now(timezone.utc).isoformat(),
            }
            loop = asyncio.get_event_loop()
            loop.run_in_executor(None, notify, payload)
            # Kritik eşik (0.7) aşıldıysa araca tanımlı alıcıya e-posta
            if result["anomaly_score"] >= 0.7:
                from app.services.mailer import kritik_anomali_bildir
                loop.run_in_executor(None, kritik_anomali_bildir,
                    eq_id, result["anomaly_score"], payload["description"],
                    rul_tahmin.get("baskin_sensor"), rul_tahmin.get("rul_saat"))
            loop.run_in_executor(
                None, store_anomaly,
                result["description"] or "anomali",
                {"equipment_id": eq_id, "score": result["anomaly_score"]},
            )

        # Metan/İSG alarm üretimi kaldırıldı — kapsam kararı: sistemin İSG
        # katkısı "ekipman arızasını önlemek"tir; gaz izleme ayrı modül.
        # gas değeri DB'ye yazılmaya devam eder ama alarm/bildirim üretmez.
        await db.commit()

    # Redis: canlı dashboard için son durum (60 sn TTL)
    await redis_client.setex(
        f"latest:{eq_id}", 60,
        json.dumps({**reading, **result, "gas_status": gas_eval}),
    )


def _on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        client.subscribe(TOPIC, qos=1)
        print(f"MQTT subscriber bağlandı → {MQTT_HOST}:{MQTT_PORT}  (abone: {TOPIC})")
    else:
        print(f"MQTT bağlantı hatası: {reason_code}")


def _on_message(client, userdata, msg):
    """paho thread'inde çalışır → işi ana event loop'a devret."""
    try:
        reading = json.loads(msg.payload.decode())
    except Exception:
        return
    if _loop and _loop.is_running():
        asyncio.run_coroutine_threadsafe(_handle_reading(reading), _loop)


def start(loop: asyncio.AbstractEventLoop):
    """FastAPI startup'ta çağrılır. Subscriber'ı arka thread'de başlatır."""
    global _client, _loop
    _loop = loop
    _client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="maden-subscriber",
    )
    _client.on_connect = _on_connect
    _client.on_message = _on_message
    _client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    _client.loop_start()


def stop():
    global _client
    if _client:
        _client.loop_stop()
        _client.disconnect()
        _client = None


def status() -> dict:
    """Subscriber bağlantı durumu (dashboard için)."""
    connected = bool(_client and _client.is_connected())
    return {
        "baglanti":  "aktif" if connected else "kapalı",
        "broker":    f"{MQTT_HOST}:{MQTT_PORT}",
        "topic":     TOPIC,
        "protokol":  "MQTT 3.1.1 (Eclipse Mosquitto)",
    }
