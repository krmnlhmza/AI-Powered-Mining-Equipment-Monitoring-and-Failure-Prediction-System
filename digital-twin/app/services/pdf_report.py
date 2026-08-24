"""
PDF Rapor Üretici
------------------
Son N saatteki anomalileri ve sistem özetini bir PDF dosyasına döker.
Jüri için "PDF Report" entegrasyonunun somut çıktısı.

  build_anomaly_report(rows, summary, hours) → bytes (PDF içeriği)

Kullanım: app/routers/reports.py içinden çağrılır, StreamingResponse ile
indirilebilir dosya olarak sunulur.
"""

from datetime import datetime, timezone
from io import BytesIO
from typing import List, Dict
from fpdf import FPDF


# Renk paleti — koyu mavi başlık, açık gri zebra satır, kritik kırmızı
COLOR_HEADER  = (30, 58, 95)
COLOR_ACCENT  = (37, 99, 235)
COLOR_ROW_ALT = (245, 247, 250)
COLOR_CRIT    = (220, 38, 38)
COLOR_TEXT    = (30, 41, 59)
COLOR_MUTE    = (100, 116, 139)


class _Report(FPDF):
    """A4 rapor şablonu. (Adım 7) Helvetica yerine DejaVu kullanılır:
    Helvetica gömülü Türkçe karakter içermez, "KRİTİK" → "KR?T?K" oluyordu.
    DejaVu özgür lisanslı bir Unicode fonttur; fonts/ klasöründen gömülür,
    böylece PDF her bilgisayarda (Docker dahil) aynı görünür."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_font("DejaVu", "",  "fonts/DejaVuSans.ttf")
        self.add_font("DejaVu", "B", "fonts/DejaVuSans-Bold.ttf")

    def header(self):
        self.set_fill_color(*COLOR_HEADER)
        self.rect(0, 0, 210, 22, "F")
        self.set_text_color(255, 255, 255)
        self.set_font("DejaVu", "B", 14)
        self.set_xy(10, 6)
        self.cell(0, 6, "Maden Dijital İkiz — Anomali Raporu", align="L")
        self.set_font("DejaVu", "", 8)
        self.set_xy(10, 13)
        self.cell(0, 5, "ÇankaYazılım | TEKNOFEST 2026 Maden Teknolojileri",
                  align="L")
        self.set_text_color(*COLOR_TEXT)
        self.ln(18)

    def footer(self):
        self.set_y(-14)
        self.set_font("DejaVu", "", 7)
        self.set_text_color(*COLOR_MUTE)
        self.cell(0, 5, f"Otomatik üretildi: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                  align="L")
        self.cell(0, 5, f"Sayfa {self.page_no()}", align="R")


def build_anomaly_report(rows: List[Dict], summary: Dict, hours: int,
                         rul_bilgileri: List[Dict] = None,
                         rag_onerileri: List[Dict] = None) -> bytes:
    """
    rows    : recent_anomalies endpoint'inden gelen liste
              (her satırda: time, equipment_id, anomaly_score, description, resolved)
    summary : dashboard/summary endpoint'inden gelen özet
              (toplam_okuma, anomali_24h, anomali_1h)
    hours   : raporun kapsadığı saat aralığı (üst başlığa yazılır)
    """
    pdf = _Report(format="A4")
    pdf.add_page()

    # ── ÖZET KUTUSU ──────────────────────────────────────
    pdf.set_font("DejaVu", "B", 11)
    pdf.set_text_color(*COLOR_HEADER)
    pdf.cell(0, 7, f"Sistem Özeti (son {hours} saat)", ln=1)
    pdf.set_draw_color(*COLOR_ACCENT)
    pdf.set_line_width(0.4)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    pdf.set_font("DejaVu", "", 10)
    pdf.set_text_color(*COLOR_TEXT)
    box_w = 60
    box_h = 18
    y0 = pdf.get_y()
    for i, (label, value, color) in enumerate([
        ("Toplam Okuma",       summary.get("toplam_okuma", 0),  COLOR_ACCENT),
        ("Anomali (24 saat)",  summary.get("anomali_24h", 0),   COLOR_CRIT),
        ("Anomali (son 1 saat)", summary.get("anomali_1h", 0),  (245, 158, 11)),
    ]):
        x = 10 + i * (box_w + 5)
        pdf.set_fill_color(248, 250, 252)
        pdf.set_draw_color(220, 226, 235)
        pdf.rect(x, y0, box_w, box_h, "DF")
        pdf.set_xy(x + 3, y0 + 3)
        pdf.set_font("DejaVu", "", 8)
        pdf.set_text_color(*COLOR_MUTE)
        pdf.cell(box_w - 6, 4, label.upper())
        pdf.set_xy(x + 3, y0 + 8)
        pdf.set_font("DejaVu", "B", 15)
        pdf.set_text_color(*color)
        pdf.cell(box_w - 6, 8, str(value))
    pdf.set_y(y0 + box_h + 8)
    pdf.set_text_color(*COLOR_TEXT)

    # ── ANOMALİ TABLOSU ──────────────────────────────────
    pdf.set_font("DejaVu", "B", 11)
    pdf.set_text_color(*COLOR_HEADER)
    pdf.cell(0, 7, f"Anomali Detayları ({len(rows)} kayıt)", ln=1)
    pdf.set_draw_color(*COLOR_ACCENT)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(3)

    if not rows:
        pdf.set_font("DejaVu", "", 10)
        pdf.set_text_color(*COLOR_MUTE)
        pdf.cell(0, 8, "Bu aralıkta anomali kaydı bulunmuyor. Sistem normal.", ln=1)
    else:
        # Başlık satırı
        pdf.set_fill_color(*COLOR_HEADER)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("DejaVu", "B", 9)
        widths = [26, 30, 16, 16, 102]   # zaman, ekipman, skor, durum, açıklama
        headers = ["Zaman", "Ekipman", "Skor", "Durum", "Açıklama"]
        for w, h in zip(widths, headers):
            pdf.cell(w, 8, h, fill=True, align="L")
        pdf.ln()

        # Veri satırları
        pdf.set_font("DejaVu", "", 8)
        for i, row in enumerate(rows):
            fill = (i % 2 == 0)
            if fill:
                pdf.set_fill_color(*COLOR_ROW_ALT)
            pdf.set_text_color(*COLOR_TEXT)

            ts = row.get("time", "")
            try:
                # ISO string → "12.05 14:32" gibi kısa format
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                ts_str = dt.strftime("%d.%m %H:%M")
            except Exception:
                ts_str = str(ts)[:16]

            score = float(row.get("anomaly_score", 0))
            score_str = f"{score:.2f}"
            status = "ÇÖZÜLDÜ" if row.get("resolved") else "AÇIK"
            desc = (row.get("description") or "").replace("\n", " ").strip()
            # (Adım 7) ASCII zorlaması kaldırıldı — DejaVu Türkçe'yi destekler
            if len(desc) > 95:
                desc = desc[:92] + "..."

            # Skor sütununda kritik kırmızı renk
            row_cells = [
                (widths[0], ts_str, None),
                (widths[1], row.get("equipment_id", ""), None),
                (widths[2], score_str, COLOR_CRIT if score >= 0.8 else None),
                (widths[3], status, COLOR_MUTE if status == "ÇÖZÜLDÜ" else (245, 158, 11)),
                (widths[4], desc, None),
            ]
            for w, text, color in row_cells:
                if color:
                    pdf.set_text_color(*color)
                else:
                    pdf.set_text_color(*COLOR_TEXT)
                pdf.cell(w, 7, str(text), fill=fill, align="L")
            pdf.ln()

    # ── ARIZA TAHMİNİ (LSTM) BÖLÜMÜ ─────────────────────
    if rul_bilgileri:
        pdf.ln(5)
        pdf.set_font("DejaVu", "B", 11)
        pdf.set_text_color(*COLOR_HEADER)
        pdf.cell(0, 7, "Arıza Tahmini — Kalan Faydalı Ömür (LSTM)", ln=1)
        pdf.set_draw_color(*COLOR_ACCENT)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(3)
        pdf.set_font("DejaVu", "", 9)
        for r in rul_bilgileri:
            renk = COLOR_CRIT if r.get("durum") == "KRİTİK" else                    (245, 158, 11) if r.get("durum") == "UYARI" else (22, 101, 52)
            pdf.set_text_color(*COLOR_TEXT)
            pdf.cell(60, 7, f"{r['equipment_id']}")
            pdf.set_text_color(*renk)
            pdf.cell(40, 7, f"{r.get('durum','—')}")
            pdf.set_text_color(*COLOR_TEXT)
            pdf.cell(0, 7, f"kalan ömür ~{r.get('rul_saat','—')} saat · izlenen: {r.get('baskin_sensor','—')}", ln=1)

    # ── SERVİS ASİSTANI ÖNERİLERİ (RAG) ──────────────────
    if rag_onerileri:
        pdf.ln(5)
        pdf.set_font("DejaVu", "B", 11)
        pdf.set_text_color(*COLOR_HEADER)
        pdf.cell(0, 7, "Servis Asistanı Önerileri (RAG)", ln=1)
        pdf.set_draw_color(*COLOR_ACCENT)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(3)
        pdf.set_font("DejaVu", "", 9)
        for o in rag_onerileri:
            pdf.set_text_color(*COLOR_TEXT)
            pdf.multi_cell(0, 6, f"• {o['baslik']}" +
                           (f"  (Parça no: {o['parcalar']})" if o.get("parcalar") else ""))

    # ── ALT BİLGİ ────────────────────────────────────────
    pdf.ln(6)
    pdf.set_font("DejaVu", "", 8)
    pdf.set_text_color(*COLOR_MUTE)
    pdf.multi_cell(0, 4,
        "Bu rapor, Isolation Forest tabanlı anomali tespiti ve LSTM tabanlı "
        "kalan ömür tahmini sisteminden otomatik üretilmiştir. Sandvik LH517i "
        "ve TH551i ekipmanlarının canlı sensör verisi değerlendirilmiştir. "
        "Detaylı incelemeler için /docs API arayüzünü kullanın.")

    # bytes olarak döndür (StreamingResponse için)
    return bytes(pdf.output(dest="S"))
