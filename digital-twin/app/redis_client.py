"""
Redis İstemcisi (Async)
------------------------
Canlı dashboard'un "şu anki son durum" için kullandığı önbellek.
Her sensör okumasında `latest:{equipment_id}` anahtarına 60 sn TTL ile yazılır;
demo arayüzü 1–2 saniyede bir buradan okur (DB'yi yormamak için).
"""

import redis.asyncio as redis
from dotenv import load_dotenv
import os

load_dotenv()

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True,
)
