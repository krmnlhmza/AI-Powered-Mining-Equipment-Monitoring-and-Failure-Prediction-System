"""
E-posta Servisi (SMTP)
-----------------------
Kritik anomali bildirimleri (araç bazlı alıcı) ve PDF raporu e-postası.

Neden backend'de? n8n'in e-posta düğümü bu sürümde CLI-import ile sessizce
çalışmadı; smtplib yolu ise doğrudan test edilip kanıtlandı. n8n zinciri
(webhook → log) durur; e-postanın sahibi backend'dir — tek, güvenilir yol.

Kimlik bilgisi .env'den okunur (SMTP_USER / SMTP_PASS). .env git'e girmez;
şifre repoda ASLA yer almaz. Şifre yoksa servis sessizce devre dışı kalır.
"""

import os
import smtplib
import ssl
from email.message import EmailMessage

import certifi
from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")

# Araç → alıcı eşlemesi (kritik anomali bildirimleri).
# Adresler .env üzerinden tanımlanır; kaynak kodda kişisel veri tutulmaz.
# Biçim:  ALARM_ALICILARI="LH517i_001:bakim@ornek.com,LH517i_002:sef@ornek.com"
# Listede olmayan araç için e-posta gönderilmez (ör. TH551i_001).
def _arac_alici_haritasi() -> dict:
    ham = os.getenv("ALARM_ALICILARI", "")
    harita = {}
    for parca in ham.split(","):
        if ":" in parca:
            arac, adres = parca.split(":", 1)
            arac, adres = arac.strip(), adres.strip()
            if arac and adres:
                harita[arac] = adres
    return harita


ARAC_ALICI = _arac_alici_haritasi()

# Sistem raporu alıcıları (virgülle ayrılmış); tanımsızsa alarm alıcıları kullanılır.
RAPOR_ALICILAR = [a.strip() for a in os.getenv("RAPOR_ALICILARI", "").split(",") if a.strip()] \
                 or list(dict.fromkeys(ARAC_ALICI.values()))


def _gonder(alicilar: list, konu: str, metin: str,
            ek_ad: str = None, ek_icerik: bytes = None) -> bool:
    """SMTP üzerinden e-posta gönderir. Başarıyı bool döner, asla exception
    fırlatmaz (bildirim hatası ana akışı durdurmamalı)."""
    if not SMTP_USER or not SMTP_PASS:
        print("mailer: SMTP kimliği tanımlı değil (.env: SMTP_USER/SMTP_PASS) — gönderim atlandı")
        return False
    try:
        msg = EmailMessage()
        msg["From"] = SMTP_USER
        msg["To"] = ", ".join(alicilar)
        msg["Subject"] = konu
        msg.set_content(metin)
        if ek_ad and ek_icerik:
            msg.add_attachment(ek_icerik, maintype="application",
                               subtype="pdf", filename=ek_ad)
        ctx = ssl.create_default_context(cafile=certifi.where())
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx, timeout=25) as s:
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        print(f"mailer: e-posta gönderildi → {alicilar} ({konu})")
        return True
    except Exception as e:
        print(f"mailer: gönderim hatası: {type(e).__name__}: {e}")
        return False


# Aynı arıza olayı 4-6 okuma sürer; her okumada ayrı mail atmamak için
# araç başına soğuma süresi uygulanır (olay başına TEK bildirim).
_son_bildirim: dict = {}
BILDIRIM_SOGUMA_SN = 600   # 10 dakika


def kritik_anomali_bildir(eq_id: str, skor: float, aciklama: str,
                          supheli: str = None, rul_saat=None) -> bool:
    """Kritik anomali (skor >= 0.7) e-postası — araca tanımlı alıcıya.
    Olay başına tek mail: soğuma süresi dolmadan tekrar göndermez."""
    import time
    alici = ARAC_ALICI.get(eq_id)
    if not alici:
        return False   # bu araç için e-posta bildirimi tanımlı değil
    if time.time() - _son_bildirim.get(eq_id, 0) < BILDIRIM_SOGUMA_SN:
        return False   # aynı olay için zaten bildirildi
    _son_bildirim[eq_id] = time.time()
    govde = (
        f"Ekipman: {eq_id}\n"
        f"Anomali skoru: {skor}\n"
        f"Şüpheli bileşen: {supheli or 'analiz ediliyor'}\n"
        f"Tahmini kalan ömür: {str(rul_saat) + ' saat' if rul_saat else 'hesaplanıyor'}\n\n"
        f"Açıklama:\n{aciklama}\n\n"
        f"— Maden Ekipman İzleme Sistemi (otomatik bildirim)"
    )
    return _gonder([alici], f"[KRİTİK ANOMALİ] {eq_id} — skor {skor}", govde)


def rapor_gonder(pdf_bytes: bytes, dosya_adi: str, ozet: str) -> bool:
    """Sistem raporunu PDF ekiyle tüm rapor alıcılarına gönderir."""
    govde = (
        "Maden Ekipman İzleme Sistemi — periyodik durum raporu ektedir.\n\n"
        + ozet +
        "\n\n— Otomatik oluşturulmuştur."
    )
    return _gonder(RAPOR_ALICILAR, "Maden Dijital İkiz — Sistem Raporu",
                   govde, ek_ad=dosya_adi, ek_icerik=pdf_bytes)
