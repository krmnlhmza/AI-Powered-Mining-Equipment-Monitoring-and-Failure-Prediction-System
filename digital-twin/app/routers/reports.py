"""
Raporlama Router'ı  —  /reports/...
------------------------------------
Son N saatteki sistem durumunun indirilebilir PDF raporu.

  GET /reports/pdf?saat=24   →  application/pdf indirme
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from datetime import datetime, timedelta, timezone
from io import BytesIO

from app.database import get_db
from app.models.sensor import SensorReading, AnomalyLog
from app.services.pdf_report import build_anomaly_report

router = APIRouter(prefix="/reports", tags=["Raporlama"])


async def _rapor_verisi(db: AsyncSession, saat: int):
    """Rapor verisini toplar: özet + anomaliler + LSTM durumu + RAG önerileri.
    Hem PDF indirme hem e-posta ucu bu TEK fonksiyonu kullanır."""
    since = datetime.now(timezone.utc) - timedelta(hours=saat)
    total = await db.scalar(select(func.count()).select_from(SensorReading))
    a24 = await db.scalar(select(func.count()).select_from(AnomalyLog)
        .where(AnomalyLog.time >= datetime.now(timezone.utc) - timedelta(hours=24)))
    a1 = await db.scalar(select(func.count()).select_from(AnomalyLog)
        .where(AnomalyLog.time >= datetime.now(timezone.utc) - timedelta(hours=1)))
    summary = {"toplam_okuma": total or 0, "anomali_24h": a24 or 0, "anomali_1h": a1 or 0}

    rows = await db.execute(select(AnomalyLog).where(AnomalyLog.time >= since)
                            .order_by(desc(AnomalyLog.time)).limit(60))
    items = [{"time": l.time.isoformat() if l.time else "", "equipment_id": l.equipment_id,
              "anomaly_score": l.anomaly_score, "description": l.description,
              "resolved": l.resolved} for l in rows.scalars().all()]

    # LSTM: her aracın güncel kalan ömür durumu
    from app.services.lstm_predictor import predict_rul, SEQ_LEN
    from data.simulator import EQUIPMENT_PROFILES
    rul_bilgileri = []
    for eq_id in EQUIPMENT_PROFILES:
        r = await db.execute(select(SensorReading)
            .where(SensorReading.equipment_id == eq_id)
            .order_by(desc(SensorReading.time)).limit(SEQ_LEN))
        okumalar = list(reversed(r.scalars().all()))
        if len(okumalar) >= SEQ_LEN:
            seq = [[o.temperature, o.vibration, o.pressure, o.current, o.speed]
                   for o in okumalar]
            t = predict_rul(seq, eq_id)
            if "rul_saat" in t:
                rul_bilgileri.append({"equipment_id": eq_id, **t})

    # RAG: son anomalilere karşılık gelen teknik doküman önerileri
    rag_onerileri, gorulen = [], set()
    try:
        from app.services.rag_service import query as rag_query
        for it in items[:3]:
            desc_txt = (it["description"] or "").split("||")[0][:120]
            if not desc_txt:
                continue
            for hit in rag_query(desc_txt, limit=1):
                if hit["title"] not in gorulen:
                    gorulen.add(hit["title"])
                    rag_onerileri.append({"baslik": hit["title"],
                                          "parcalar": ", ".join(hit["part_numbers"][:3])})
    except Exception:
        pass
    return items, summary, rul_bilgileri, rag_onerileri


@router.get("/pdf")
async def anomaly_pdf(
    saat: int = Query(default=24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
):
    """Son `saat` saatin zengin PDF raporu (özet + anomaliler + LSTM + RAG)."""
    items, summary, rul_b, rag_o = await _rapor_verisi(db, saat)
    pdf_bytes = build_anomaly_report(items, summary, saat,
                                     rul_bilgileri=rul_b, rag_onerileri=rag_o)
    filename = f"anomali_raporu_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    return StreamingResponse(BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.post("/email")
async def anomaly_report_email(
    saat: int = Query(default=24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
):
    """Zengin raporu üretir ve PDF ekiyle rapor alıcılarına e-postalar."""
    from app.services.mailer import rapor_gonder, RAPOR_ALICILAR
    items, summary, rul_b, rag_o = await _rapor_verisi(db, saat)
    pdf_bytes = build_anomaly_report(items, summary, saat,
                                     rul_bilgileri=rul_b, rag_onerileri=rag_o)
    ozet = (f"Kapsam: son {saat} saat\n"
            f"Toplam okuma: {summary['toplam_okuma']}\n"
            f"Anomali (24 sa): {summary['anomali_24h']} · (1 sa): {summary['anomali_1h']}")
    import asyncio as _a
    ok = await _a.get_event_loop().run_in_executor(None, rapor_gonder,
        pdf_bytes, f"anomali_raporu_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf", ozet)
    return {"gonderildi": ok, "alicilar": RAPOR_ALICILAR if ok else []}
