"""
OPC-UA Adapter — Modern endüstriyel haberleşme standardı (IEC 62541).

Sandvik gibi büyük üreticilerin yeni nesil kontrolcüleri OPC-UA sunucu
çalıştırır. Bu adapter, server'a "client" olarak bağlanır, makinelere
ait `Equipment/{id}/Sensors/{ad}` düğümlerini okur.

Düğüm yolu şeması (mock server ile uyumlu):

  ns=2;s=Equipment.{equipment_id}.Sensors.Temperature   → Float (°C)
  ns=2;s=Equipment.{equipment_id}.Sensors.Vibration     → Float (mm/s)
  ns=2;s=Equipment.{equipment_id}.Sensors.Pressure      → Float (bar)
  ns=2;s=Equipment.{equipment_id}.Sensors.Current       → Float (A)
  ns=2;s=Equipment.{equipment_id}.Sensors.Speed         → Float (km/h)
  ns=2;s=Equipment.{equipment_id}.Sensors.Gas           → Float (%)

Modbus'tan farkı: gerçek floating point veri tipleri, hiyerarşik
namespace, metadata (isim/açıklama/birim) ve abone olmaya hazır
DataChange notification altyapısı. Sahada güçlü sebep: tek IP'den
yüzlerce makinenin tüm sensörleri tek bağlantıda toparlanır.
"""

import os
from typing import Optional, Dict

from app.adapters.base import BaseAdapter


# OPC-UA düğüm yolu şablonu
NS_INDEX = 2
NODE_TEMPLATE = "ns=2;s=Equipment.{eq}.Sensors.{sensor}"

SENSOR_FIELDS = ["Temperature", "Vibration", "Pressure",
                 "Current",     "Speed",     "Gas"]


class OPCUAAdapter(BaseAdapter):
    name     = "opcua"
    protocol = "OPC-UA (IEC 62541)"

    def __init__(self):
        self.host = os.getenv("OPCUA_HOST", "localhost")
        self.port = int(os.getenv("OPCUA_PORT", 4840))
        self.url  = f"opc.tcp://{self.host}:{self.port}/cankayazilim/"
        self.endpoint = self.url

    async def test_connection(self) -> bool:
        try:
            from asyncua import Client
            client = Client(self.url, timeout=2)
            await client.connect()
            await client.disconnect()
            return True
        except Exception:
            return False

    async def read_once(self, equipment_id: str) -> Optional[Dict]:
        try:
            from asyncua import Client
            client = Client(self.url, timeout=3)
            await client.connect()

            reading: Dict = {
                "equipment_id":   equipment_id,
                "equipment_type": "loader" if "LH" in equipment_id else "truck",
            }
            try:
                for field in SENSOR_FIELDS:
                    node_id = NODE_TEMPLATE.format(eq=equipment_id, sensor=field)
                    node = client.get_node(node_id)
                    val  = await node.read_value()
                    # Düğüm adlarını standart snake_case'e dönüştür
                    reading[field.lower()] = round(float(val), 3)
            finally:
                await client.disconnect()

            reading["kaynak"] = f"OPC-UA @ {self.url}"
            return reading

        except ConnectionRefusedError:
            return {"hata": f"OPC-UA sunucusuna bağlanılamadı ({self.url}). "
                            "scripts/mock_opcua_server.py çalışıyor mu?"}
        except Exception as e:
            return {"hata": f"OPC-UA okuma hatası: {e}"}

    def status(self) -> Dict:
        base = super().status()
        base["namespace"] = NS_INDEX
        base["sensor_count_per_equipment"] = len(SENSOR_FIELDS)
        return base
