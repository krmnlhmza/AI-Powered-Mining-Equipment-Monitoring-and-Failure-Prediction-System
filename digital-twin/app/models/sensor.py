"""
Veritabanı Modelleri (SQLAlchemy ORM)
--------------------------------------
PostgreSQL + TimescaleDB üzerinde iki tablo:

  SensorReading  — her sensör okumasının kalıcı kaydı (zaman serisi).
  AnomalyLog     — tespit edilen anomalilerin ayrı log tablosu (çözüldü
                   bayrağı, açıklama, Qdrant referansı dahil).
"""

from sqlalchemy import Column, String, Float, DateTime, Boolean, Integer, Text
from sqlalchemy.sql import func
from app.database import Base


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    time = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    equipment_id = Column(String(50), nullable=False, index=True)
    equipment_type = Column(String(50), nullable=False)  # conveyor, pump, crusher
    temperature = Column(Float)
    vibration = Column(Float)
    pressure = Column(Float)
    current = Column(Float)
    speed = Column(Float)
    gas = Column(Float, default=0.0)   # % CH4 — kayıt sürer, alarm üretmez
    rpm = Column(Float)                # devir (d/dk)
    torque = Column(Float)             # tork (Nm)
    fuel = Column(Float)               # yakıt tüketimi (L/sa)
    is_anomaly = Column(Boolean, default=False)
    anomaly_score = Column(Float, default=0.0)


class AnomalyLog(Base):
    __tablename__ = "anomaly_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    time = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    equipment_id = Column(String(50), nullable=False)
    equipment_type = Column(String(50), nullable=False)
    anomaly_score = Column(Float)
    description = Column(Text)
    embedding_id = Column(String(100))  # Qdrant point id
    resolved = Column(Boolean, default=False)
