"""
Modbus TCP Adapter — Endüstriyel PLC ve sürücülerle haberleşme.

Sahadaki tipik kurgu: Sandvik LH517i üzerindeki kontrolcü (örn.
Beckhoff/Siemens PLC) sensör değerlerini holding register'larında
tutar. Bu adapter belirli bir Slave ID üzerinden register'ları okur,
ham int değerleri ölçeklendirip standart sensör dict'ine çevirir.

Register şeması (mock sunucu ile uyumlu):

  Slave ID = ekipmanın indeksi (1..N)
  Register | Anlam            | Ölçek
  ---------+------------------+--------------------------------
  100      | sıcaklık         | int * 10   → °C       (876 → 87.6)
  101      | titreşim         | int * 100  → mm/s     (250 → 2.50)
  102      | basınç           | int        → bar      (268 → 268)
  103      | akım             | int        → A        (175 → 175)
  104      | hız              | int * 10   → km/h     (52  → 5.2)
  105      | metan (CH4)      | int * 1000 → %        (400 → 0.400)

Gerçek sahada bu eşleme PLC üreticisinden gelir; biz mock sunucumuzda
da aynı şemayı uygulayarak adapter'ın doğruluğunu kanıtlıyoruz.
"""

import os
from typing import Optional, Dict, List

from app.adapters.base import BaseAdapter


# Register haritası (offset değeri = base + sensor offset)
REGISTER_MAP = {
    "temperature": (100, 10.0),
    "vibration":   (101, 100.0),
    "pressure":    (102, 1.0),
    "current":     (103, 1.0),
    "speed":       (104, 10.0),
    "gas":         (105, 1000.0),
}

# Ekipman ID → Slave ID eşlemesi (PLC adresleri)
EQUIPMENT_SLAVES = {
    "LH517i_001": 1,
    "LH517i_002": 2,
    "TH551i_001": 3,
}


class ModbusAdapter(BaseAdapter):
    name     = "modbus"
    protocol = "Modbus TCP/IP (IEC 61158)"

    def __init__(self):
        self.host = os.getenv("MODBUS_HOST", "localhost")
        self.port = int(os.getenv("MODBUS_PORT", 5020))
        self.endpoint = f"{self.host}:{self.port}"

    async def test_connection(self) -> bool:
        try:
            from pymodbus.client import AsyncModbusTcpClient
            client = AsyncModbusTcpClient(self.host, port=self.port)
            ok = await client.connect()
            if ok:
                client.close()
            return ok
        except Exception:
            return False

    async def read_once(self, equipment_id: str) -> Optional[Dict]:
        """Bir PLC slave'inden 6 register okuyup standart dict'e çevirir."""
        slave_id = EQUIPMENT_SLAVES.get(equipment_id)
        if slave_id is None:
            return {"hata": f"Bilinmeyen ekipman: {equipment_id}"}

        try:
            from pymodbus.client import AsyncModbusTcpClient
            client = AsyncModbusTcpClient(self.host, port=self.port)
            if not await client.connect():
                return {"hata": f"Modbus sunucusuna bağlanılamadı ({self.endpoint}). "
                                "scripts/mock_modbus_server.py çalışıyor mu?"}

            reading: Dict = {
                "equipment_id":   equipment_id,
                "equipment_type": "loader" if "LH" in equipment_id else "truck",
            }

            for key, (reg_addr, scale) in REGISTER_MAP.items():
                resp = await client.read_holding_registers(
                    address=reg_addr, count=1, slave=slave_id,
                )
                if resp.isError():
                    reading[key] = None
                else:
                    raw = resp.registers[0]
                    reading[key] = round(raw / scale, 3)

            reading["kaynak"] = f"Modbus TCP slave#{slave_id} @ {self.endpoint}"
            client.close()
            return reading

        except Exception as e:
            return {"hata": f"Modbus okuma hatası: {e}"}

    def status(self) -> Dict:
        base = super().status()
        base["slave_count"] = len(EQUIPMENT_SLAVES)
        base["register_count"] = len(REGISTER_MAP)
        return base
