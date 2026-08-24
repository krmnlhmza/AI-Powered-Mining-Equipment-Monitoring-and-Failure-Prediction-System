"""
Sahte Modbus TCP Sunucusu — Sandvik PLC Taklidi
─────────────────────────────────────────────────
Gerçek bir PLC olmadan Modbus adapter'ımızı kanıtlamak için.
Her ekipman için Slave ID atar, simülatörden gelen sensör
değerlerini PLC register şemasına göre 100-105 adreslerinden sunar.

Çalıştırma:
  python scripts/mock_modbus_server.py

Sonra dashboard'dan veya terminalden:
  curl -X POST "http://localhost:8000/adapters/modbus/test?ekipman=LH517i_001"
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusSlaveContext,
    ModbusServerContext,
)
from pymodbus.server import StartAsyncTcpServer

from data.simulator import generate_reading, EQUIPMENT_PROFILES
from app.adapters.modbus_adapter import REGISTER_MAP, EQUIPMENT_SLAVES


def _build_initial_context() -> ModbusServerContext:
    """Her slave için ilk register değerlerini simülatörden hazırla."""
    slaves = {}
    for eq_id, slave_id in EQUIPMENT_SLAVES.items():
        # Register 0-199 hepsi 0 başlasın, sonra 100-105 atanır
        block = ModbusSequentialDataBlock(0, [0] * 200)
        slaves[slave_id] = ModbusSlaveContext(
            di=block, co=block, hr=block, ir=block, zero_mode=True,
        )
    return ModbusServerContext(slaves=slaves, single=False)


async def _updater(context: ModbusServerContext):
    """Her ~2 saniyede bir register değerlerini taze sensör verisiyle güncelle."""
    print("📡 Mock Modbus güncelleyici başladı (2 sn aralık).")
    while True:
        for eq_id, slave_id in EQUIPMENT_SLAVES.items():
            reading = generate_reading(eq_id)
            slave_ctx = context[slave_id]
            for sensor, (reg_addr, scale) in REGISTER_MAP.items():
                val = reading.get(sensor, 0.0) or 0.0
                raw = int(round(val * scale))
                # Modbus register'ları 16-bit unsigned: 0–65535
                raw = max(0, min(65535, raw))
                # function code 3 (holding registers) — context altında "h"
                slave_ctx.setValues(3, reg_addr, [raw])
        await asyncio.sleep(2)


async def _main():
    host = os.getenv("MODBUS_HOST", "0.0.0.0")
    port = int(os.getenv("MODBUS_PORT", 5020))

    print("=" * 60)
    print(f"  Sahte Modbus TCP Sunucusu — Sandvik PLC Taklidi")
    print(f"  Bağlantı: {host}:{port}")
    print(f"  Ekipman → Slave ID:")
    for eq, sid in EQUIPMENT_SLAVES.items():
        print(f"    {eq:<14} → slave#{sid}")
    print(f"  Register şeması:")
    for sensor, (addr, scale) in REGISTER_MAP.items():
        print(f"    register {addr:>4} = {sensor:<12} (÷{scale})")
    print("=" * 60)

    context = _build_initial_context()
    # Güncelleyici görevini paralel başlat
    asyncio.create_task(_updater(context))

    await StartAsyncTcpServer(context=context, address=(host, port))


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        print("\nSunucu durduruldu.")
