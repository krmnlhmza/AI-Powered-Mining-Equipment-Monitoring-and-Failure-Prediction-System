# -*- coding: utf-8 -*-
"""ÇankaYazılım — Teknik ve Ticari Rapor üretici (ortak yardımcılar).

fpdf2 tabanlı. DejaVu fontlarıyla tam Türkçe/Unicode desteği.
İçerik dosyaları: rapor_tr.py (Türkçe), rapor_en.py (English).
"""
import os
from fpdf import FPDF
from fpdf.enums import XPos, YPos

KOK   = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FONT  = os.path.join(KOK, "digital-twin", "fonts")
IMG   = os.path.join(KOK, "docs", "images")
ARAYUZ = os.path.join(IMG, "arayuz")
SEMA   = os.path.join(IMG, "semalar")

# ── Marka paleti ────────────────────────────────────────────────
PRIMARY = (13, 90, 76)      # koyu teal
ACCENT  = (216, 82, 38)     # turuncu
DARK    = (28, 32, 38)
MUTED   = (112, 118, 126)
LIGHT   = (238, 244, 242)
RED     = (176, 42, 42)
GREEN   = (26, 122, 74)
WHITE   = (255, 255, 255)

GENISLIK = 180   # kullanılabilir metin genişliği (A4, 15mm kenar)


class Rapor(FPDF):
    def __init__(self, ust_baslik: str, alt_bilgi: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.ust_baslik = ust_baslik
        self.alt_bilgi  = alt_bilgi
        self.kapak_modu = True
        self.set_auto_page_break(auto=True, margin=20)
        self.set_margins(15, 15, 15)
        self.add_font("DJ", "",  os.path.join(FONT, "DejaVuSans.ttf"))
        self.add_font("DJ", "B", os.path.join(FONT, "DejaVuSans-Bold.ttf"))
        self.set_font("DJ", "", 10)

    # ── sayfa başlığı / altlığı ──
    def header(self):
        if self.kapak_modu or self.page_no() <= 1:
            return
        self.set_y(8)
        self.set_font("DJ", "B", 8)
        self.set_text_color(*PRIMARY)
        self.cell(0, 4, "ÇankaYazılım", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("DJ", "", 7)
        self.set_text_color(*MUTED)
        self.set_y(8)
        self.cell(0, 4, self.ust_baslik, align="R",
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*PRIMARY)
        self.set_line_width(0.4)
        self.line(15, 16, 195, 16)
        self.set_y(22)

    def footer(self):
        if self.kapak_modu or self.page_no() <= 1:
            return
        self.set_y(-14)
        self.set_draw_color(220, 224, 222)
        self.set_line_width(0.2)
        self.line(15, self.get_y() - 2, 195, self.get_y() - 2)
        self.set_font("DJ", "", 7)
        self.set_text_color(*MUTED)
        self.cell(0, 4, self.alt_bilgi, align="L")
        self.set_y(-14)
        self.cell(0, 4, str(self.page_no()), align="R")

    # ── içerik yardımcıları ──
    def h1(self, no: str, metin: str):
        if self.get_y() > 225:
            self.add_page()
        self.ln(4)
        self.set_fill_color(*PRIMARY)
        self.set_text_color(*WHITE)
        self.set_font("DJ", "B", 12)
        self.cell(11, 9, no, align="C", fill=True)
        self.set_fill_color(*LIGHT)
        self.set_text_color(*PRIMARY)
        self.cell(GENISLIK - 11, 9, "  " + metin, fill=True,
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(3)
        self.set_text_color(*DARK)

    def h2(self, metin: str):
        if self.get_y() > 250:
            self.add_page()
        self.ln(2.5)
        self.set_font("DJ", "B", 10.5)
        self.set_text_color(*PRIMARY)
        self.multi_cell(GENISLIK, 5.5, metin, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(*DARK)
        self.ln(1)

    def p(self, metin: str, boyut=9.3):
        self.set_font("DJ", "", boyut)
        self.set_text_color(*DARK)
        self.multi_cell(GENISLIK, 4.7, metin, align="J",
                        new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1.6)

    def madde(self, satirlar, boyut=9.3):
        self.set_font("DJ", "", boyut)
        self.set_text_color(*DARK)
        for s in satirlar:
            y0 = self.get_y()
            if y0 > 262:
                self.add_page(); y0 = self.get_y()
            self.set_x(18)
            self.set_text_color(*ACCENT)
            self.set_font("DJ", "B", boyut)
            self.cell(4, 4.7, "•")
            self.set_text_color(*DARK)
            self.set_font("DJ", "", boyut)
            self.multi_cell(GENISLIK - 7, 4.7, s, align="J",
                            new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.ln(0.6)
        self.ln(1.2)

    def kutu(self, baslik: str, metin: str, renk=None):
        renk = renk or ACCENT
        self.set_font("DJ", "", 9)
        satir = self.multi_cell(GENISLIK - 10, 4.5, metin, dry_run=True,
                                output="LINES", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        yuk = 9 + len(satir) * 4.5
        if self.get_y() + yuk > 268:
            self.add_page()
        y0 = self.get_y()
        self.set_fill_color(250, 246, 243)
        self.rect(15, y0, GENISLIK, yuk, style="F")
        self.set_fill_color(*renk)
        self.rect(15, y0, 1.6, yuk, style="F")
        self.set_xy(20, y0 + 2.5)
        self.set_font("DJ", "B", 9)
        self.set_text_color(*renk)
        self.cell(GENISLIK - 10, 4.5, baslik, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_x(20)
        self.set_font("DJ", "", 9)
        self.set_text_color(*DARK)
        self.multi_cell(GENISLIK - 10, 4.5, metin, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_y(y0 + yuk + 3)

    def kpi(self, ogeler):
        """ogeler: [(buyuk_deger, aciklama), ...] — en fazla 4"""
        n = len(ogeler)
        w = GENISLIK / n
        if self.get_y() + 20 > 268:
            self.add_page()
        y0 = self.get_y()
        for i, (deger, aciklama) in enumerate(ogeler):
            x = 15 + i * w
            self.set_fill_color(*LIGHT)
            self.rect(x + 1, y0, w - 2, 19, style="F")
            self.set_xy(x + 1, y0 + 2.5)
            self.set_font("DJ", "B", 15)
            self.set_text_color(*PRIMARY)
            self.cell(w - 2, 8, deger, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.set_xy(x + 2, y0 + 11)
            self.set_font("DJ", "", 7)
            self.set_text_color(*MUTED)
            self.multi_cell(w - 4, 3.3, aciklama, align="C",
                            new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_y(y0 + 23)
        self.set_text_color(*DARK)

    def tablo(self, basliklar, satirlar, genislikler, baslik_rengi=None, boyut=7.8):
        baslik_rengi = baslik_rengi or PRIMARY
        # başlık satırı
        if self.get_y() + 20 > 268:
            self.add_page()
        self.set_font("DJ", "B", boyut)
        self.set_fill_color(*baslik_rengi)
        self.set_text_color(*WHITE)
        yuk_b = 6.5
        for b, w in zip(basliklar, genislikler):
            self.cell(w, yuk_b, " " + b, border=0, fill=True, align="L")
        self.ln(yuk_b)
        # gövde
        self.set_font("DJ", "", boyut)
        self.set_text_color(*DARK)
        acik = True
        for satir in satirlar:
            # satır yüksekliği
            gerekli = 1
            for h, w in zip(satir, genislikler):
                ln = self.multi_cell(w - 2, 3.9, str(h), align="L", dry_run=True,
                                     output="LINES", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                gerekli = max(gerekli, len(ln))
            yuk = gerekli * 3.9 + 2.6
            if self.get_y() + yuk > 272:
                self.add_page()
                self.set_font("DJ", "B", boyut)
                self.set_fill_color(*baslik_rengi)
                self.set_text_color(*WHITE)
                for b, w in zip(basliklar, genislikler):
                    self.cell(w, yuk_b, " " + b, fill=True, align="L")
                self.ln(yuk_b)
                self.set_font("DJ", "", boyut)
                self.set_text_color(*DARK)
            y0 = self.get_y()
            self.set_fill_color(*(LIGHT if acik else WHITE))
            self.rect(15, y0, sum(genislikler), yuk, style="F")
            x = 15
            for h, w in zip(satir, genislikler):
                self.set_xy(x + 1, y0 + 1.3)
                self.multi_cell(w - 2, 3.9, str(h), align="L",
                                new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                x += w
            self.set_y(y0 + yuk)
            acik = not acik
        self.ln(2.5)

    def gorsel(self, yol: str, altyazi: str, genislik=None, max_yuk=100):
        if not os.path.exists(yol):
            return
        from PIL import Image
        with Image.open(yol) as im:
            oran = im.height / im.width
        g = genislik or GENISLIK
        y = g * oran
        if max_yuk and y > max_yuk:
            y = max_yuk
            g = y / oran
        if self.get_y() + y + 8 > 272:
            self.add_page()
        x = 15 + (GENISLIK - g) / 2
        self.image(yol, x=x, y=self.get_y(), w=g)
        self.set_y(self.get_y() + y + 1.5)
        self.set_font("DJ", "", 7.4)
        self.set_text_color(*MUTED)
        self.multi_cell(GENISLIK, 3.6, altyazi, align="C",
                        new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(*DARK)
        self.ln(2.5)

    # ── kapak ──
    def kapak(self, baslik, altbaslik, etiket, yazar_blok, tarih, iletisim):
        self.kapak_modu = True
        self.add_page()
        self.set_fill_color(*PRIMARY)
        self.rect(0, 0, 210, 62, style="F")
        # Kelime markası (logo kullanılmaz)
        self.set_xy(15, 24)
        self.set_font("DJ", "B", 26)
        self.set_text_color(*WHITE)
        self.cell(0, 12, "ÇankaYazılım", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_x(15)
        self.set_font("DJ", "", 9)
        self.set_text_color(214, 232, 226)
        self.cell(0, 5, "Endüstriyel Yapay Zeka  ·  Industrial AI",
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.set_xy(15, 84)
        self.set_font("DJ", "B", 19)
        self.set_text_color(*DARK)
        self.multi_cell(180, 9.5, baslik, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(3)
        self.set_x(15)
        self.set_font("DJ", "", 12)
        self.set_text_color(*ACCENT)
        self.multi_cell(180, 6, altbaslik, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.ln(6)
        self.set_x(15)
        self.set_font("DJ", "", 8.6)
        self.set_text_color(*MUTED)
        self.multi_cell(180, 4.6, etiket, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.set_xy(15, 214)
        self.set_draw_color(*PRIMARY)
        self.set_line_width(0.5)
        self.line(15, 212, 195, 212)
        self.set_font("DJ", "B", 9.6)
        self.set_text_color(*DARK)
        self.multi_cell(180, 5, yazar_blok, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)
        self.set_x(15)
        self.set_font("DJ", "", 8.6)
        self.set_text_color(*MUTED)
        self.multi_cell(180, 4.4, iletisim, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(2)
        self.set_x(15)
        self.set_font("DJ", "", 8.2)
        self.cell(0, 4, tarih)
        self.kapak_modu = False
