"""
Sensör Okuması İşleme Hattı (tek kaynak)
-----------------------------------------
MQTT abonesi (app.services.mqtt_subscriber) ve HTTP uç noktası
(POST /sensors/reading, /sensors/simulate) AYNI fonksiyonu kullanır. Böylece
iki giriş yolu arasında davranış farkı (ör. birinde e-posta gidip ötekinde
gitmemesi) oluşamaz.

    okuma → anomali tespiti (NBM artığı + Isolation Forest, 3 ardışık teyit)
          → TimescaleDB kaydı
          → yeni olay ise: otomatik RUL tahmini + AnomalyLog
          → Redis son durum (latest:{eq})  ·  canlı akış (SSE, /dashboard/stream)
          → yeni olay ise (arka planda): n8n bildirimi, Qdrant'a embedding,
            kritik skorda (≥ 0.7) e-posta

Metan değeri kaydedilir ve `gas_status` olarak panele iletilir; alarm
üretmez (kapsam kararı — gaz izleme ayrı modül).
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from app.models.sensor import AnomalyLog, SensorReading
from app.services import events

log = logging.getLogger("pipeline")

# DB'ye yazılan sensör kolonları (op_hours, phase, wear_level yalnız akışta taşınır)
TEMEL = ["temperature", "vibration", "pressure", "current", "speed"]
EK = ["rpm", "torque", "fuel"]


async def otomatik_tahmin(db, eq_id: str, guncel: list = None) -> tuple:
    """OTOMATİK ARIZA TAHMİNİ (anomali → RUL zinciri).

    Anomali yakalanınca RUL LSTM'e sorulur: "hangi bileşen bozuluyor, ne kadar
    ömür kaldı?" Dönüş: (uyarı metnine eklenecek cümle, ham tahmin dict'i)"""
    from app.services.lstm_predictor import predict_rul
    try:
        rul = await asyncio.get_running_loop().run_in_executor(None, predict_rul, eq_id)
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
        log.warning("otomatik RUL tahmini yapılamadı: %s", e)
        return "", {}


def _background(func, *args):
    """Bloklayan yan etkileri (HTTP, SMTP, embedding) olay döngüsünü tutmadan
    çalıştırır. Bildirim hatası veri hattını durdurmaz."""
    def run():
        try:
            func(*args)
        except Exception as exc:
            log.warning("%s başarısız: %s", getattr(func, "__name__", func), exc)
    asyncio.get_running_loop().run_in_executor(None, run)


def _num(v) -> Optional[float]:
    return None if v is None else float(v)


async def process_reading(reading: dict, db=None) -> SensorReading:
    """Tek bir sensör okumasını uçtan uca işler ve DB kaydını döner.

    `db` verilirse o oturum kullanılır (HTTP isteği); verilmezse kendi
    oturumunu açar (MQTT abonesi)."""
    from app.database import AsyncSessionLocal
    from app.redis_client import redis_client
    from app.services.anomaly_detector import detect as detect_anomaly, yeni_olay_mu
    from data.simulator import gas_status

    eq_id = reading.get("equipment_id", "unknown")
    eq_type = reading.get("equipment_type")
    now = datetime.now(timezone.utc)

    result = detect_anomaly(reading)
    # Tek olay = tek alarm: episod boyunca yalnız ilk anomali okumasında tetikle
    yeni_olay = yeni_olay_mu(eq_id, result["is_anomaly"])
    gas_val = float(reading.get("gas") or 0.0)
    gas_eval = gas_status(gas_val)

    record = SensorReading(
        time=now,
        equipment_id=eq_id,
        equipment_type=eq_type,
        **{k: float(reading[k]) for k in TEMEL},
        **{k: _num(reading.get(k)) for k in EK},
        gas=gas_val,
        is_anomaly=result["is_anomaly"],
        anomaly_score=result["anomaly_score"],
    )

    own_session = db is None
    session = AsyncSessionLocal() if own_session else db
    alarm: Optional[AnomalyLog] = None
    rul_tahmin: dict = {}
    temel_aciklama = result["description"] or "anomali"
    try:
        session.add(record)
        if yeni_olay:
            tahmin_metni, rul_tahmin = await otomatik_tahmin(
                session, eq_id, [reading[k] for k in TEMEL])
            result["description"] = (result["description"] or "") + tahmin_metni
            alarm = AnomalyLog(
                time=now, equipment_id=eq_id, equipment_type=eq_type,
                anomaly_score=result["anomaly_score"], description=result["description"],
            )
            session.add(alarm)
        await session.commit()
        await session.refresh(record)
        if alarm is not None:
            await session.refresh(alarm)
    finally:
        if own_session:
            await session.close()

    # Canlı durum: Redis (polling yedeği) + SSE (anlık)
    canli = {**reading, **result, "gas_status": gas_eval, "time": now.isoformat()}
    try:
        await redis_client.setex(f"latest:{eq_id}", 60, json.dumps(canli, default=str))
    except Exception as exc:
        log.debug("Redis yazılamadı: %s", exc)
    events.publish({"type": "reading", "data": canli})

    if alarm is not None:
        events.publish({"type": "alarm", "data": {
            "id": alarm.id, "time": now.isoformat(), "equipment_id": eq_id,
            "anomaly_score": round(float(alarm.anomaly_score), 3),
            "description": alarm.description, "resolved": False,
        }})
        _bildir(eq_id, eq_type, reading, result, rul_tahmin, temel_aciklama, now)

    return record


def _bildir(eq_id, eq_type, reading, result, rul_tahmin, temel_aciklama, now):
    from app.services.embedding_service import store_anomaly
    from app.services.n8n_notifier import notify
    from app.services.anomaly_detector import KRITIK_ESIGI

    metadata = {
        "equipment_id":   eq_id,
        "equipment_type": eq_type,
        "anomaly_score":  result["anomaly_score"],
        "temperature":    reading["temperature"],
        "vibration":      reading["vibration"],
        "time":           now.isoformat(),
    }
    _background(notify, {**metadata,
                         "description": result["description"],
                         "rul_saat": rul_tahmin.get("rul_saat"),
                         "supheli_bilesen": rul_tahmin.get("baskin_sensor")})
    # Benzer-arıza araması için yalnız tespit açıklaması gömülür (tahmin metni değil)
    _background(store_anomaly, temel_aciklama, metadata)
    if result["anomaly_score"] >= KRITIK_ESIGI:
        from app.services.mailer import kritik_anomali_bildir
        _background(kritik_anomali_bildir, eq_id, result["anomaly_score"],
                    result["description"], rul_tahmin.get("baskin_sensor"),
                    rul_tahmin.get("rul_saat"))
