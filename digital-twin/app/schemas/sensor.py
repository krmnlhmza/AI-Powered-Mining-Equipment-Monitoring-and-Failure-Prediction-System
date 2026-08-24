"""
API Şemaları (Pydantic)
------------------------
HTTP istek/yanıtlarının veri şekillerini tanımlar. DB modellerinden
(app/models/sensor.py) ayrı tutulur ki API kontratı veritabanı kolonlarına
sıkı bağlı kalmasın.

  SensorReadingCreate      — POST /sensors/reading gövdesi
  SensorReadingOut         — okuma yanıtı (id, time, anomali alanları dahil)
  AnomalyLogOut            — anomali listesi yanıtı
  AnomalyDetectionResult   — iç servis dönüş şekli
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class SensorReadingCreate(BaseModel):
    equipment_id: str
    equipment_type: str
    temperature: float
    vibration: float
    pressure: float
    current: float
    speed: float
    gas: float = 0.0   # % CH4 (metan)
    rpm: Optional[float] = None      # devir (d/dk)
    torque: Optional[float] = None   # tork (Nm)
    fuel: Optional[float] = None     # yakıt tüketimi (L/sa)


class SensorReadingOut(SensorReadingCreate):
    id: int
    time: datetime
    gas: Optional[float] = None
    is_anomaly: bool
    anomaly_score: float

    model_config = {"from_attributes": True}


class AnomalyLogOut(BaseModel):
    id: int
    time: datetime
    equipment_id: str
    equipment_type: str
    anomaly_score: float
    description: Optional[str]
    resolved: bool

    model_config = {"from_attributes": True}


class AnomalyDetectionResult(BaseModel):
    is_anomaly: bool
    anomaly_score: float
    equipment_id: str
    description: Optional[str] = None
