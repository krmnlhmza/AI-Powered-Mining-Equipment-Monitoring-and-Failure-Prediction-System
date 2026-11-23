"""
MQTT Sensör Abonesi (Subscriber)
---------------------------------
Backend'in veri giriş katmanı. Mosquitto broker'a abone olur, `maden/+/sensor`
topic'lerinden gelen her sensör mesajını alır ve işler:

    MQTT mesajı → app.services.pipeline.process_reading
                  (anomali tespiti → DB → Redis + SSE → alarm/bildirim)

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


async def _handle_reading(reading: dict):
    """Tek bir sensör okumasını işler (ana event loop'ta çalışır).
    Tüm iş ortak veri hattındadır — HTTP yolu da aynı fonksiyonu kullanır."""
    from app.services.pipeline import process_reading
    try:
        await process_reading(reading)
    except Exception as e:
        print(f"  MQTT okuması işlenemedi ({reading.get('equipment_id')}): {e}")


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
