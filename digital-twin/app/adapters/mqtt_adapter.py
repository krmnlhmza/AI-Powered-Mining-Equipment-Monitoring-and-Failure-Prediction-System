"""
MQTT Adapter — sahadaki MQTT gateway/broker'a abone olarak veri alır.
Mevcut canlı akış zaten MQTT üzerinden çalışıyor (app/services/mqtt_subscriber);
bu sınıf onu adapter arayüzüne uydurur ki diğer protokollerle aynı şekilde
listelenip test edilebilsin.
"""

import os
import socket
import json
from typing import Optional, Dict

from app.adapters.base import BaseAdapter


class MQTTAdapter(BaseAdapter):
    name     = "mqtt"
    protocol = "MQTT 3.1.1 (Eclipse Mosquitto)"

    def __init__(self):
        self.host = os.getenv("MQTT_HOST", "localhost")
        self.port = int(os.getenv("MQTT_PORT", 1883))
        self.endpoint = f"{self.host}:{self.port}"

    async def test_connection(self) -> bool:
        """MQTT broker TCP portu açık mı? Hızlı kontrol."""
        try:
            with socket.create_connection((self.host, self.port), timeout=2):
                return True
        except OSError:
            return False

    async def read_once(self, equipment_id: str) -> Optional[Dict]:
        """
        MQTT'de canlı yayın olduğundan, Redis'teki son okumayı geri döner —
        bu, "abone olan adapter'ın az önce aldığı en son mesaj"a eşdeğerdir.
        """
        try:
            from app.redis_client import redis_client
            cached = await redis_client.get(f"latest:{equipment_id}")
            if not cached:
                return None
            data = json.loads(cached)
            # Adapter sözleşmesine uydur (standard alanlar)
            return {
                "equipment_id":   data.get("equipment_id", equipment_id),
                "equipment_type": data.get("equipment_type"),
                "temperature":    data.get("temperature"),
                "vibration":      data.get("vibration"),
                "pressure":       data.get("pressure"),
                "current":        data.get("current"),
                "speed":          data.get("speed"),
                "gas":            data.get("gas"),
                "kaynak":         "MQTT canlı yayın (Redis cache)",
            }
        except Exception as e:
            return {"hata": f"MQTT okuma hatası: {e}"}

    def status(self) -> Dict:
        base = super().status()
        # mqtt_subscriber'dan gerçek bağlantı durumu
        try:
            from app.services import mqtt_subscriber
            sub_status = mqtt_subscriber.status()
            base["baglanti"] = sub_status.get("baglanti", "bilinmiyor")
            base["topic"]    = sub_status.get("topic", "")
        except Exception:
            base["baglanti"] = "bilinmiyor"
        return base
