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

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List
from datetime import datetime, timedelta, timezone
import json

from app.database import get_db
from app.models.sensor import SensorReading
from app.schemas.sensor import SensorReadingCreate, SensorReadingOut
from app.services.pipeline import process_reading
from app.redis_client import redis_client
from data.simulator import generate_reading

router = APIRouter(prefix="/sensors", tags=["Sensörler"])


def _bilinen_ekipman(equipment_id: str):
    """Bilinmeyen ekipman 404 döner. (Aksi hâlde dedektör ilk profile düşer ve
    o makinenin akış durumunu — EWMA, devreye alma ortalaması — bozardı.)"""
    from data.simulator import EQUIPMENT_PROFILES
    if equipment_id not in EQUIPMENT_PROFILES:
        raise HTTPException(status_code=404, detail=f"Bilinmeyen ekipman: {equipment_id}")


@router.post("/reading", response_model=SensorReadingOut)
async def add_reading(data: SensorReadingCreate, db: AsyncSession = Depends(get_db)):
    """Harici sistemden okuma. MQTT yoluyla AYNI veri hattı işler
    (app.services.pipeline): tespit → kayıt → Redis/SSE → alarm/bildirim."""
    _bilinen_ekipman(data.equipment_id)
    return await process_reading(data.model_dump(), db)


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
    force_anomaly: bool = False,
    force_gas: bool = False,
    ariza_tipi: str = None,   # (Senaryo 2) hedefli arıza: vibration_spike | overheat
    db: AsyncSession = Depends(get_db),
):
    _bilinen_ekipman(equipment_id)
    reading = generate_reading(equipment_id, force_anomaly=force_anomaly,
                               force_gas=force_gas, fault_type=ariza_tipi)
    SensorReadingCreate(**reading)   # şema doğrulaması
    # Ham okuma (phase, wear_level dahil) iletilir: 3D ikiz faz bilgisini kullanır
    return await process_reading(reading, db)


@router.post("/maintenance/{equipment_id}")
async def do_maintenance(equipment_id: str, bilesen: str | None = None):
    """Bakım: bileşeni (ya da hepsini) yenile — hasar sıfırlanır.
    Canlı Test'te başlatılan arıza artık kendiliğinden kaybolmaz; bakımla giderilir."""
    from data.simulator import EQUIPMENT_PROFILES, maintenance
    if equipment_id not in EQUIPMENT_PROFILES:
        return {"hata": "bilinmeyen araç"}
    return maintenance(equipment_id, bilesen)


@router.get("/twin/{equipment_id}")
async def twin_state(equipment_id: str):
    """Dijital ikizin iç durumu (bileşen hasarları, GERÇEK RUL, olay günlüğü).
    Yalnız simülasyonda bilinen değerler içerir — değerlendirme/hata ayıklama içindir."""
    from data.simulator import EQUIPMENT_PROFILES, twin_status
    if equipment_id not in EQUIPMENT_PROFILES:
        return {"hata": "bilinmeyen araç"}
    return twin_status(equipment_id)

