"""
Sahte OPC-UA Sunucusu — Modern Sandvik PLC Taklidi
─────────────────────────────────────────────────────
asyncua ile çalışan, sensör düğümlerini canlı güncelleyen bir
OPC-UA server. Adapter'ımızın gerçek bir endüstri sunucusuyla
konuşabildiğini kanıtlar.

Düğüm hiyerarşisi:
  Equipment/
    LH517i_001/
      Sensors/
        Temperature  (Float, °C)
        Vibration    (Float, mm/s)
        Pressure     (Float, bar)
        Current      (Float, A)
        Speed        (Float, km/h)
        Gas          (Float, %)
    LH517i_002/...
    TH551i_001/...

Çalıştırma:
  python scripts/mock_opcua_server.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from asyncua import Server, ua

from data.simulator import generate_reading, EQUIPMENT_PROFILES
from app.adapters.opcua_adapter import SENSOR_FIELDS, NS_INDEX


async def _main():
    host = os.getenv("OPCUA_HOST", "0.0.0.0")
    port = int(os.getenv("OPCUA_PORT", 4840))

    server = Server()
    await server.init()
    endpoint = f"opc.tcp://{host}:{port}/cankayazilim/"
    server.set_endpoint(endpoint)
    server.set_server_name("ÇankaYazılım Mock OPC-UA Server")

    uri = "http://cankayazilim.tr/madenikiz"
    idx = await server.register_namespace(uri)
    assert idx == NS_INDEX, f"Namespace index beklenen {NS_INDEX}, alınan {idx}"

    # Klasör yapısı: Equipment/LH517i_001/Sensors/Temperature, ...
    objects = server.nodes.objects
    equipment_root = await objects.add_folder(idx, "Equipment")

    nodes = {}   # (eq_id, sensor) → node
    for eq_id in EQUIPMENT_PROFILES:
        eq_folder = await equipment_root.add_folder(
            ua.NodeId(f"Equipment.{eq_id}", idx), eq_id,
        )
        sens_folder = await eq_folder.add_folder(
            ua.NodeId(f"Equipment.{eq_id}.Sensors", idx), "Sensors",
        )
        for sensor in SENSOR_FIELDS:
            node = await sens_folder.add_variable(
                ua.NodeId(f"Equipment.{eq_id}.Sensors.{sensor}", idx),
                sensor, 0.0, ua.VariantType.Double,
            )
            await node.set_writable()
            nodes[(eq_id, sensor)] = node

    print("=" * 60)
    print(f"  Sahte OPC-UA Sunucusu — Modern Sandvik Kontrolcü Taklidi")
    print(f"  Endpoint: {endpoint}")
    print(f"  Namespace: ns={idx} ('{uri}')")
    print(f"  {len(EQUIPMENT_PROFILES)} ekipman × {len(SENSOR_FIELDS)} sensör"
          f" = {len(nodes)} düğüm")
    print("=" * 60)

    async with server:
        # Sensör düğümlerini canlı güncelle
        while True:
            for eq_id in EQUIPMENT_PROFILES:
                reading = generate_reading(eq_id)
                for sensor in SENSOR_FIELDS:
                    val = float(reading.get(sensor.lower(), 0.0) or 0.0)
                    node = nodes[(eq_id, sensor)]
                    await node.write_value(val)
            await asyncio.sleep(2)


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        print("\nSunucu durduruldu.")
