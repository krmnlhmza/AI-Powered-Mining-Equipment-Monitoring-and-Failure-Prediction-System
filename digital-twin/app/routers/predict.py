"""
LSTM tahmin endpoint'i.
Ekipmanın son SEQ_LEN ölçümüne bakarak bir sonraki değerleri tahmin eder.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db
from app.models.sensor import SensorReading
from app.services.lstm_predictor import (predict, predict_rul, SEQ_LEN,
                                         offline_degradation_demo)
from data.simulator import project_future

router = APIRouter(prefix="/predict", tags=["Tahmin (LSTM)"])


async def _recent_sequence(equipment_id: str, db: AsyncSession):
    result = await db.execute(
        select(SensorReading)
        .where(SensorReading.equipment_id == equipment_id)
        .order_by(desc(SensorReading.time))
        .limit(SEQ_LEN)
    )
    readings = result.scalars().all()
    if len(readings) < SEQ_LEN:
        raise HTTPException(
            status_code=400,
            detail=f"En az {SEQ_LEN} ölçüm gerekli, mevcut: {len(readings)}",
        )
    return [
        [r.temperature, r.vibration, r.pressure, r.current, r.speed]
        for r in reversed(readings)
    ]


@router.get("/{equipment_id}")
async def predict_next(equipment_id: str, db: AsyncSession = Depends(get_db)):
    """Son 20 okumadan 30 sn sonrası tahmini (LSTM)."""
    sequence = await _recent_sequence(equipment_id, db)
    return {"equipment_id": equipment_id, "tahmin": predict(sequence, equipment_id)}


@router.get("/rul/{equipment_id}")
async def predict_remaining_life(
    equipment_id: str,
    senaryo: str = "normal",       # normal | degradasyon
    ilerleme: float = 0.7,         # degradasyon: ömrün hangi noktası (0-1)
    bilesen: str | None = None,    # degradasyon: bozulacak bileşen (ör. rulman)
):
    """Kalan Faydalı Ömür (RUL).
    - senaryo=normal: makinenin canlı çalışma-saati özetlerinden
    - senaryo=degradasyon: yeni bir sanal makinede sondan sona bozulma;
      gerçek RUL ile karşılaştırmalı (modelin dürüst sınaması)"""
    if senaryo == "degradasyon":
        return offline_degradation_demo(equipment_id, ilerleme=ilerleme, bilesen=bilesen)
    result = predict_rul(equipment_id)
    result["senaryo"] = "gerçek zamanlı (canlı veri)"
    return result


@router.get("/projeksiyon/{equipment_id}")
async def future_projection(equipment_id: str, saat: float = 100.0):
    """Dijital ikiz projeksiyonu: başlamış hasarları ortalama döngü stresiyle
    `saat` çalışma saati ileri sarar."""
    return project_future(equipment_id, saat)
