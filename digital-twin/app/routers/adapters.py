"""
Adapter Router'ı  —  /adapters/...
-----------------------------------
Saha veri alma katmanını dış dünyaya açar.

  GET  /adapters                    → tüm adapter'lar + bağlantı durumu
  POST /adapters/{ad}/test          → ?ekipman=... ile canlı okuma yap

Demo akışı: jüri demo.html'de "Modbus test et" butonuna basar →
backend ilgili adapter'ı canlı çağırır → sahanın gerçek protokolünden
gelen sensör değerini ekranda gösterir. Veri kaynağı değişti (MQTT →
Modbus) ama backend hiç değişmedi — soyutlamanın gücü.
"""

from fastapi import APIRouter, HTTPException, Query
from app.adapters import registry

router = APIRouter(prefix="/adapters", tags=["Saha Veri Alma"])


@router.get("/")
async def list_adapters():
    """Tüm adapter'lar ve canlı bağlantı durumu (dashboard kartı için)."""
    return {"adapterler": await registry.list_status()}


@router.post("/{name}/test")
async def test_adapter(name: str, ekipman: str = Query(...)):
    """
    Belirli bir adapter'dan bir kez okuma yapar.
    Jüri demosu: "Modbus" → Modbus mock sunucusundan canlı veri.
    """
    if name not in registry.ADAPTERS:
        raise HTTPException(
            status_code=404,
            detail=f"Adapter bulunamadı: {name}. "
                   f"Mevcut: {list(registry.ADAPTERS.keys())}",
        )

    adapter = registry.get(name)
    reading = await adapter.read_once(ekipman)
    return {
        "adapter":  adapter.name,
        "protokol": adapter.protocol,
        "hedef":    adapter.endpoint,
        "ekipman":  ekipman,
        "okuma":    reading,
    }
