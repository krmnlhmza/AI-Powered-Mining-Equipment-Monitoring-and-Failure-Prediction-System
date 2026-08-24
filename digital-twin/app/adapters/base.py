"""
Saha Veri Alma Katmanı — Ortak Arayüz (BaseAdapter)
─────────────────────────────────────────────────────
Backend, sensör verisinin **hangi protokolden** geldiğini bilmek
zorunda değil. Bu soyutlama sayesinde:

  • MQTT (mevcut: simülatör → MQTT → subscriber)
  • Modbus TCP/RTU (PLC'ler, sürücüler)
  • OPC-UA (modern endüstri SCADA)
  • CAN-bus, Profinet, EtherCAT ... (ileride eklenebilir)

aynı arayüzü konuştuğu sürece backend kodunda **tek bir satır** dahi
değişmeden veri kaynağı değiştirilebilir.

Her adapter aşağıdaki sözleşmeyi yerine getirir:

  • name           — sabit kısa kimlik ("mqtt", "modbus", "opcua")
  • protocol       — insan-okunur protokol etiketi
  • endpoint       — bağlantı hedefi ("localhost:1883" vb.)
  • test_connection() → bool   : ulaşılabilir mi?
  • read_once(equipment_id)    → dict | None : bir okuma getir
  • status()       → dict      : dashboard için anlık durum
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict


class BaseAdapter(ABC):
    """Tüm saha veri alma katmanlarının üreteceği ortak arayüz."""

    name: str        = "base"
    protocol: str    = "Base Protocol"
    endpoint: str    = ""

    # ── Bağlantı sınaması ─────────────────────────────────────
    @abstractmethod
    async def test_connection(self) -> bool:
        """Hedefe TCP/UDP/serial seviyesinde ulaşılabiliyor mu?"""
        ...

    # ── Tek seferlik okuma ────────────────────────────────────
    @abstractmethod
    async def read_once(self, equipment_id: str) -> Optional[Dict]:
        """
        Bir ekipmandan tek bir sensör okuması döner.
        Backend'in beklediği standart anahtar şeması:

          {equipment_id, equipment_type,
           temperature, vibration, pressure, current, speed, gas}

        Adapter, kendi protokol/register şemasını **bu standarda
        çevirmekle** yükümlüdür. Bağlantı yoksa None döner.
        """
        ...

    # ── Dashboard için durum ──────────────────────────────────
    def status(self) -> Dict:
        return {
            "ad":       self.name,
            "protokol": self.protocol,
            "hedef":    self.endpoint,
        }
