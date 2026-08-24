"""
Adapter Kaydı — sistemde tanımlı tüm saha veri alma adapter'larını
tek noktadan keşfedilebilir kılar.

  ADAPTERS         — name → instance eşlemesi
  get(name)        — isme göre adapter
  list_status(...) — dashboard için tüm adapter'ların anlık durumu
"""

from typing import Dict, List

from app.adapters.base import BaseAdapter
from app.adapters.mqtt_adapter   import MQTTAdapter
from app.adapters.modbus_adapter import ModbusAdapter
from app.adapters.opcua_adapter  import OPCUAAdapter


# Tek bir örnek (singleton) — her HTTP isteğinde yeniden kurulum yok
ADAPTERS: Dict[str, BaseAdapter] = {
    "mqtt":   MQTTAdapter(),
    "modbus": ModbusAdapter(),
    "opcua":  OPCUAAdapter(),
}


def get(name: str) -> BaseAdapter:
    return ADAPTERS[name]


async def list_status() -> List[Dict]:
    """Dashboard kartları için: her adapter'ın anlık bağlantı durumu."""
    out = []
    for name, ad in ADAPTERS.items():
        st = ad.status()
        st["baglanti"] = "aktif" if await ad.test_connection() else "kapalı"
        out.append(st)
    return out
