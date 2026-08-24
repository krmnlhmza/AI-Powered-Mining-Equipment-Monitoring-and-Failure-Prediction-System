"""
Anomali Embedding Servisi
--------------------------
Tespit edilen her anomali açıklamasını yerel bir Sentence-Transformer modeliyle
384 boyutlu vektöre dönüştürüp Qdrant'a yazar. Böylece "geçmişte benzer bir
arıza yaşandı mı?" sorusu vektör benzerliğiyle (cosine) cevaplanabilir.

  • store_anomaly(description, metadata)  → kaydeder, point id döner
  • search_similar(description, limit=5)  → en yakın geçmiş arızaları döner

Koleksiyon: "anomaly_logs" (RAG bilgi tabanından ayrı).
"""

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from dotenv import load_dotenv
import os
import uuid

load_dotenv()

COLLECTION_NAME = "anomaly_logs"
VECTOR_SIZE = 1024   # turkish-e5-large (rag_service ile aynı model/boyut)

_encoder: SentenceTransformer = None
_qdrant: QdrantClient = None


def _get_encoder() -> SentenceTransformer:
    global _encoder
    if _encoder is None:
        # (Adım 6) rag_service ile AYNI yerli model (YTÜ Turkish-E5) —
        # tek model belleğe bir kez yüklenir, iki servis paylaşır.
        from app.services.rag_service import _get_encoder as rag_encoder
        _encoder = rag_encoder()
    return _encoder


def _get_qdrant() -> QdrantClient:
    global _qdrant
    if _qdrant is None:
        _qdrant = QdrantClient(
            host=os.getenv("QDRANT_HOST", "localhost"),
            port=int(os.getenv("QDRANT_PORT", 6333)),
        )
        _ensure_collection(_qdrant)
    return _qdrant


def _ensure_collection(client: QdrantClient):
    existing = [c.name for c in client.get_collections().collections]
    # Model değişmişse (vektör boyutu farklıysa) eski koleksiyon çöptür:
    # sil, yeni boyutla kur. Geçmiş anomali hafızası sıfırlanır — sorun değil,
    # canlı akış onu dakikalar içinde yeniden doldurur.
    if COLLECTION_NAME in existing:
        if client.get_collection(COLLECTION_NAME).config.params.vectors.size != VECTOR_SIZE:
            client.delete_collection(COLLECTION_NAME)
            existing.remove(COLLECTION_NAME)
    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


def store_anomaly(description: str, metadata: dict) -> str:
    encoder = _get_encoder()
    qdrant = _get_qdrant()
    embedding = encoder.encode(description).tolist()
    point_id = str(uuid.uuid4())
    qdrant.upsert(
        collection_name=COLLECTION_NAME,
        points=[PointStruct(id=point_id, vector=embedding, payload=metadata)],
    )
    return point_id


def search_similar(description: str, limit: int = 5) -> list:
    encoder = _get_encoder()
    qdrant = _get_qdrant()
    embedding = encoder.encode(description).tolist()
    response = qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=embedding,
        limit=limit,
    )
    return [{"score": r.score, "payload": r.payload} for r in response.points]
