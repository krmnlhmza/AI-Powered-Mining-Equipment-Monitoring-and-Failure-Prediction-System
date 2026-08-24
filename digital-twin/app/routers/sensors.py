"""
Sensör Router'ı  —  /sensors/...
---------------------------------
HTTP üzerinden sensör okuması ekleme, son durum ve geçmiş sorgulama,
ve simüle okuma üretme endpoint'leri.

  POST /sensors/reading            → harici sistem okuma gönderir
  GET  /sensors/latest/{eq_id}     → Redis'ten son durum
  GET  /sensors/history/{eq_id}    → DB'den geçmiş (saat parametresi ile)
  POST /sensors/simulate/{eq_id}   → simülatörden okuma üret + işlet (demo)

Bu router, MQTT akışına alternatif/yedek bir veri giriş yoludur.
Saha kanalları MQTT üzerinden besleniyor; bu endpoint'ler ise test ve
manuel demo içindir.
"""

from fastapi import APIRouter, Depends, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List
from datetime import datetime, timedelta, timezone
import json
import asyncio

from app.database import get_db
from app.models.sensor import SensorReading, AnomalyLog
from app.schemas.sensor import SensorReadingCreate, SensorReadingOut
from app.services.anomaly_detector import detect as detect_anomaly
from app.redis_client import redis_client
from data.simulator import generate_reading

router = APIRouter(prefix="/sensors", tags=["Sensörler"])


def _save_to_qdrant(description: str, metadata: dict):
    try:
        from app.services.embedding_service import store_anomaly
        store_anomaly(description, metadata)
    except Exception:
        pass


def _notify_n8n(payload: dict):
    try:
        from app.services.n8n_notifier import notify
        notify(payload)
    except Exception:
        pass


@router.post("/reading", response_model=SensorReadingOut)
async def add_reading(
    data: SensorReadingCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    from data.simulator import gas_status
    from app.services.anomaly_detector import yeni_olay_mu

    result   = detect_anomaly(data.model_dump())
    gas_eval = gas_status(float(data.gas or 0.0))
    # Tek olay = tek alarm: episod boyunca yalnız ilk anomali okumasında tetikle
    yeni_olay = yeni_olay_mu(data.equipment_id, result["is_anomaly"])

    record = SensorReading(
        **data.model_dump(),
        is_anomaly=result["is_anomaly"],
        anomaly_score=result["anomaly_score"],
    )
    db.add(record)

    if yeni_olay:
        # Otomatik arıza tahmini (MQTT yoluyla AYNI zincir — tek yardımcı)
        from app.services.mqtt_subscriber import otomatik_tahmin
        tahmin_metni, rul_tahmin = await otomatik_tahmin(
            db, data.equipment_id,
            [data.temperature, data.vibration, data.pressure, data.current, data.speed])
        result["description"] = (result["description"] or "") + tahmin_metni

        log = AnomalyLog(
            equipment_id=data.equipment_id,
            equipment_type=data.equipment_type,
            anomaly_score=result["anomaly_score"],
            description=result["description"],
        )
        db.add(log)

        metadata = {
            "equipment_id":   data.equipment_id,
            "equipment_type": data.equipment_type,
            "anomaly_score":  result["anomaly_score"],
            "temperature":    data.temperature,
            "vibration":      data.vibration,
            "time":           datetime.now(timezone.utc).isoformat(),
        }
        background_tasks.add_task(_save_to_qdrant, result["description"], metadata)
        background_tasks.add_task(_notify_n8n, {**metadata,
            "description": result["description"],
            "rul_saat": rul_tahmin.get("rul_saat"),
            "supheli_bilesen": rul_tahmin.get("baskin_sensor")})
        if result["anomaly_score"] >= 0.7:
            from app.services.mailer import kritik_anomali_bildir
            background_tasks.add_task(kritik_anomali_bildir,
                data.equipment_id, result["anomaly_score"], result["description"],
                rul_tahmin.get("baskin_sensor"), rul_tahmin.get("rul_saat"))

    # Metan/İSG alarmı kaldırıldı — kapsam kararı.

    await db.commit()
    await db.refresh(record)

    await redis_client.setex(
        f"latest:{data.equipment_id}",
        60,
        json.dumps({**data.model_dump(), **result, "gas_status": gas_eval}),
    )

    return record


@router.get("/latest/{equipment_id}")
async def get_latest(equipment_id: str):
    cached = await redis_client.get(f"latest:{equipment_id}")
    if cached:
        return json.loads(cached)
    return {"detail": "Veri bulunamadı"}


@router.get("/history/{equipment_id}", response_model=List[SensorReadingOut])
async def get_history(
    equipment_id: str,
    hours: int = Query(default=1, ge=1, le=72),
    db: AsyncSession = Depends(get_db),
):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(SensorReading)
        .where(SensorReading.equipment_id == equipment_id)
        .where(SensorReading.time >= since)
        .order_by(desc(SensorReading.time))
        .limit(500)
    )
    return result.scalars().all()


# (Senaryo 1) Fiziksel koşul seçimi — Türkçe etiketler arayüzde de kullanılır
FAZ_ETIKETLERI = {
    "idle": "Bekleme (rölanti)", "approach_pile": "Yığına yaklaşma",
    "picking_up": "Kepçe doldurma", "hauling_loaded": "Yüklü taşıma",
    "approach_dump": "Boşaltmaya yaklaşma", "dumping": "Boşaltma",
    "returning_empty": "Boş dönüş",
    "idle_waiting": "Bekleme", "getting_loaded": "Yüklenme",
    "accelerating_loaded": "Yüklü hızlanma", "climbing_loaded": "Yokuş yukarı (yüklü)",
    "arriving_dump": "Boşaltmaya yaklaşma", "descending_empty": "Yokuş aşağı (boş)",
    "accelerating_empty": "Boş hızlanma",
}


@router.get("/mode/{equipment_id}")
async def get_modes(equipment_id: str):
    """Araç için seçilebilir fiziksel koşullar + aktif mod (Senaryo 1).
    Liste araç tipine göre değişir; kaynak simulator.MANUAL_SCENARIOS."""
    from data.simulator import EQUIPMENT_PROFILES, manual_scenarios_for, _get_state
    if equipment_id not in EQUIPMENT_PROFILES:
        return {"hata": "bilinmeyen araç"}
    eq_type = EQUIPMENT_PROFILES[equipment_id]["type"]
    fazlar = [{"kod": kod, "ad": ad} for kod, ad in manual_scenarios_for(eq_type)]
    st = _get_state(equipment_id)
    return {"fazlar": fazlar, "aktif": st.manual_phase or "auto"}


@router.post("/mode/{equipment_id}")
async def set_mode(equipment_id: str, faz: str = Query(...)):
    """(Senaryo 1) Fiziksel koşulu sabitle: faz=kotu_yol | climbing_loaded | ... | auto"""
    from data.simulator import EQUIPMENT_PROFILES, manual_scenarios_for, set_manual_phase
    if equipment_id not in EQUIPMENT_PROFILES:
        return {"hata": "bilinmeyen araç"}
    eq_type = EQUIPMENT_PROFILES[equipment_id]["type"]
    etiketler = dict(manual_scenarios_for(eq_type))
    if faz != "auto" and faz not in etiketler:
        return {"hata": f"geçersiz koşul: {faz}"}
    set_manual_phase(equipment_id, faz)
    return {"equipment_id": equipment_id, "mod": faz,
            "ad": "Otomatik döngü" if faz == "auto" else etiketler.get(faz, faz)}


@router.post("/simulate/{equipment_id}", response_model=SensorReadingOut)
async def simulate_reading(
    equipment_id: str,
    background_tasks: BackgroundTasks,   # DİKKAT: varsayılan DEĞER VERME!
    # FastAPI, BackgroundTasks'i yalnız varsayılansız parametrede enjekte eder;
    # `= BackgroundTasks()` yazılırsa görevler kuyruğa alınır ama ASLA çalışmaz
    # (e-posta/n8n bildirimlerinin sessizce kaybolduğu hatanın kök nedeni buydu).
    force_anomaly: bool = False,
    force_gas: bool = False,
    ariza_tipi: str = None,   # (Senaryo 2) hedefli arıza: vibration_spike | overheat
    db: AsyncSession = Depends(get_db),
):
    reading = generate_reading(equipment_id, force_anomaly=force_anomaly,
                               force_gas=force_gas, fault_type=ariza_tipi)
    schema  = SensorReadingCreate(**reading)
    return await add_reading(schema, background_tasks, db)
