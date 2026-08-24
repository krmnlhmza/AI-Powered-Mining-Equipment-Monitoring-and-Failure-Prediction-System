import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager

from app.database import init_db
from app.routers import sensors, anomalies, predict
from app.routers import dashboard
from app.routers import rag
from app.routers import reports
from app.routers import adapters as adapters_router
from data.simulator import EQUIPMENT_PROFILES

# Tek doğruluk kaynağı: simülatördeki ekipman profilleri.
# Ekipman eklemek/çıkarmak için sadece data/simulator.py'deki
# EQUIPMENT_PROFILES sözlüğü güncellenir; burası otomatik takip eder.
EQUIPMENT_IDS = list(EQUIPMENT_PROFILES.keys())
_stream_task  = None


async def _live_stream():
    """
    Saha sensörlerini taklit eden MQTT yayıncısı.
    Her 3 saniyede tüm ekipmanlar için okuma üretir ve MQTT broker'a yayınlar.
    (Demo akıcılığı için 3 sn: grafikler daha sık nokta alır, veri "canlı" akar.)
    Veriyi tüketip işleyen taraf app.services.mqtt_subscriber'dır.
    Akış:  simülatör → MQTT (maden/{eq}/sensor) → subscriber → DB/Redis/n8n/Qdrant
    """
    from data.mqtt_publisher import make_client, publish_reading
    import random

    # Yayıncı bağlanana kadar kısa bekleme
    await asyncio.sleep(2)
    client = await asyncio.get_event_loop().run_in_executor(None, make_client)
    client.loop_start()
    print("MQTT publisher başladı (canlı yayın).")

    # Otomatik anomali/metan enjeksiyonu KAPALIDIR: arıza yalnız arayüzdeki
    # Canlı Test senaryolarıyla (manuel) tetiklenir — demo tamamen kontrollü.
    try:
        while True:
            await asyncio.sleep(3)
            for eq_id in EQUIPMENT_IDS:
                publish_reading(client, eq_id)
    except asyncio.CancelledError:
        pass
    finally:
        client.loop_stop()
        client.disconnect()


# ── n8n workflow kurulumu (Adım 7 notu) ─────────────────────────────
# Eskiden burada, açılışta n8n REST API'sine workflow yükleyen ~100 satırlık
# bir fonksiyon vardı (_setup_n8n). Yeni n8n sürümleri bu eski basic-auth
# API'yi kabul etmediği için her açılışta SESSİZCE başarısız oluyordu (ölü kod).
# Workflow artık kalıcı olarak n8n'in kendi veritabanında kuruludur.
# Yeniden kurmak gerekirse (ör. n8n volume silinirse):
#   docker cp n8n_workflows/anomali_alarm.json n8n:/tmp/wf.json
#   docker exec n8n n8n import:workflow --input=/tmp/wf.json
#   docker exec n8n n8n update:workflow --id=AnomaliAlarm2026 --active=true
#   docker restart n8n
# ─────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Modelleri ön yükle (ilk istek yavaş olmasın)
    from app.services.anomaly_detector import _load
    from app.services.embedding_service import _get_encoder, _get_qdrant
    from app.services.rag_service import index_knowledge
    from app.services import mqtt_subscriber
    _load()
    await asyncio.get_event_loop().run_in_executor(None, _get_encoder)
    await asyncio.get_event_loop().run_in_executor(None, _get_qdrant)
    await asyncio.get_event_loop().run_in_executor(None, index_knowledge)

    # MQTT abonesini başlat (veri giriş katmanı), ardından yayıncıyı
    mqtt_subscriber.start(asyncio.get_event_loop())

    global _stream_task
    _stream_task = asyncio.create_task(_live_stream())
    yield
    if _stream_task:
        _stream_task.cancel()
    mqtt_subscriber.stop()


app = FastAPI(
    title="Maden Dijital İkiz API",
    description="Maden ekipmanları için anomali tespiti ve tahmin sistemi",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sensors.router)
app.include_router(anomalies.router)
app.include_router(predict.router)
app.include_router(dashboard.router)
app.include_router(rag.router)
app.include_router(reports.router)
app.include_router(adapters_router.router)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    return RedirectResponse(url="/static/demo.html")


@app.get("/health")
async def health():
    return {"status": "ok"}
