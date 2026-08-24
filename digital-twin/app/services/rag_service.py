"""
RAG (Retrieval-Augmented Generation) Servisi
Sandvik LH517 teknik dokümantasyonu üzerinde semantik arama.
"""

import os
import json
from typing import List, Dict
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

COLLECTION = "sandvik_knowledge"
# (Adım 6) Millileşme hamlesi — sunum Slayt 9'daki "tamamen yerli, açık
# kaynak embedding" iddiasının karşılığı: Yıldız Teknik Üniversitesi COSMOS
# grubunun Türkçe için geliştirdiği Turkish-E5 modeli. Tamamen yerel çalışır
# (bulut yok), ilk açılışta Hugging Face'ten bir kez indirilir (~2.2 GB).
# E5 ailesi kuralı: dokümanlar "passage: ", sorgular "query: " önekiyle
# kodlanır — öneksiz kullanılırsa arama kalitesi ciddi düşer.
EMBED_MODEL = "ytu-ce-cosmos/turkish-e5-large"
GREET_ESIK = 0.76   # sohbet kapısı eşiği (ölçüm: sohbet 0.78-0.89, teknik 0.65-0.74)
_greet_centroid = None
VECTOR_SIZE = 1024   # turkish-e5-large çıktı boyutu (eski MiniLM 384 idi)

_encoder: SentenceTransformer = None
_qdrant: QdrantClient = None
_indexed = False


def _get_encoder():
    global _encoder
    if _encoder is None:
        _encoder = SentenceTransformer(EMBED_MODEL)
    return _encoder


def _get_qdrant():
    global _qdrant
    if _qdrant is None:
        _qdrant = QdrantClient(
            host=os.getenv("QDRANT_HOST", "localhost"),
            port=int(os.getenv("QDRANT_PORT", 6333)),
        )
    return _qdrant


def _ensure_collection():
    """Koleksiyonu hazırlar. (Adım 6) Önemli ders: model değişince eski
    vektörler ÇÖPTÜR — sorgu yeni modelin geometrisinde, kayıtlar eskininki.
    Haziran'da tam bu yaşandı: koleksiyon eski modelle yazılmış, kod
    "kayıt var, dokunma" deyip hiç tazelememişti; "motor aşırı ısınma"
    sorusu yangın söndürme bloğunu getiriyordu. Bu yüzden: boyut uyuşmazsa
    koleksiyon SİLİNİP yeniden kurulur (12 blok, saniyeler sürer)."""
    q = _get_qdrant()
    existing = [c.name for c in q.get_collections().collections]
    if COLLECTION in existing:
        mevcut_boyut = q.get_collection(COLLECTION).config.params.vectors.size
        if mevcut_boyut != VECTOR_SIZE:
            print(f"RAG: koleksiyon eski modelden kalma ({mevcut_boyut} boyut) — "
                  f"siliniyor, {VECTOR_SIZE} boyutla yeniden kurulacak.")
            q.delete_collection(COLLECTION)
            existing.remove(COLLECTION)
    if COLLECTION not in existing:
        q.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


# ── Bilgi Tabanı ──────────────────────────────────────────────────────────────

KNOWLEDGE_BASE = [
    # Motor ve Güç Sistemi
    {
        "id": "lh517-motor-01",
        "category": "Motor Sistemi",
        "title": "LH517 Motor ve Yağ Sıcaklığı Limitleri",
        "content": "Sandvik LH517 motor/yağ sıcaklığı normal çalışma aralığı 70-90°C arasındadır. Motor yağı sıcaklığı bu aralığı aşarsa yağ viskozitesi düşer ve yatak aşınması hızlanır. 95°C üzerinde uyarı alarmı devreye girer. 105°C üzerinde motor otomatik olarak kapatılır. Belirtiler: yağ sıcaklığı yüksek, yağ lambası yandı, hararet, makine hararet yaptı, motor kaynadı, su attı, motor çok ısınıyor/kızıyor, sıcaklık göstergesi yükseliyor, buhar/sıcak koku, radyatör buharı. Yüksek sıcaklık tespit edildiğinde: 1) Yağ ve soğutma sıvısı seviyesini kontrol edin, 2) Yağ soğutucusunu (oil cooler) ve radyatörü temizleyin, 3) Termostatı test edin, 4) Yağ değişim aralığını (500 saat) doğrulayın.",
        "part_numbers": ["56037200", "56037201"],
        "failure_mode": "aşırı ısınma",
    },
    {
        "id": "lh517-motor-02",
        "category": "Motor Sistemi",
        "title": "LH517 Motor Akım Limitleri",
        "content": "LH517 tahrik motoru nominal akım 185A, maksimum 220A'dir. Sürekli 200A üzeri akım motor sargı arızasına yol açar. Yüksek akım tespitinde: 1) Yük dağılımını kontrol edin, 2) Motor izolasyon direncini ölçün (min. 1MΩ), 3) Fırçaları ve kolektörü kontrol edin. Parça no: 56206419 (SWITCH MAIN), 56024620 (HORN).",
        "part_numbers": ["56206419", "56024620"],
        "failure_mode": "aşırı akım",
    },
    # Titreşim ve Mekanik
    {
        "id": "lh517-vibration-01",
        "category": "Titreşim ve Mekanik",
        "title": "LH517 Titreşim Eşikleri ve Rulman Bakımı",
        "content": "Sandvik LH517 normal titreşim değeri 0-4.5 mm/s RMS'dir. 5-8 mm/s arası erken uyarı bölgesidir; rulman kontrolü önerilir. 8 mm/s üzeri kritik eşik olup makine durdurulmalıdır. Belirtiler: titreme, titreşim, sarsıntı, sallanma, tıkırdama, takırtı, anormal ses/gürültü, rulman sesi, direksiyon/şasi titremesi, makine sarsıyor. Front Frame Assembly (P/N 56204783) bağlantı noktaları kontrol edilmelidir. Liftarms Bushing (P/N 56045500) 500 saat aralıklarla değiştirilmelidir.",
        "part_numbers": ["56204783", "56045500", "56045520"],
        "failure_mode": "aşırı titreşim",
    },
    {
        "id": "lh517-vibration-02",
        "category": "Titreşim ve Mekanik",
        "title": "LH517 Ön Çerçeve ve Bağlantı Parçaları",
        "content": "Front Frame Bushings (P/N 56204784): 140 D9X155 S6/LG 78 ve 155/140-88 standart tiplerdir. Busing aşınması titreşim artışına neden olur. Muayene aralığı 250 çalışma saatidir. Swing Lever Bushings (P/N 56045520) ve Dogbone (P/N 56027788) bağlantı noktaları greslenmeli; 125 saat aralıklarla kontrol edilmelidir.",
        "part_numbers": ["56204784", "56045520", "56027788"],
        "failure_mode": "titreşim, bağlantı aşınması",
    },
    # Hidrolik ve Basınç
    {
        "id": "lh517-hydraulic-01",
        "category": "Hidrolik Sistem",
        "title": "LH517 Hidrolik Basınç Değerleri",
        "content": "LH517 hidrolik sistem çalışma basıncı 250-280 bar arasındadır. Düşük basınç (200 bar altı) pompa aşınması veya filtre tıkanmasına işaret eder. Belirtiler: zorlanma, güç kaybı, makine çekmiyor, kepçe kaldırmıyor veya yavaş kalkıyor, bom gücü zayıf, hidrolik zayıfladı, kaldırma performansı düşük, ağır çalışıyor. Yüksek basınç (290 bar üzeri) relief valve arızasını gösterir. Rear Tank Assembly (P/N 56037200) hidrolik yağ haznesi kapasitesi 120 litredir. Yağ değişim aralığı 1000 çalışma saatidir.",
        "part_numbers": ["56037200", "56037201", "56028042"],
        "failure_mode": "hidrolik basınç sapması",
    },
    {
        "id": "lh517-hydraulic-pump-01",
        "category": "Hidrolik Sistem",
        "title": "LH517 Yağ / Hidrolik Pompa Arızası",
        "content": "LH517 hidrolik pompası sistem basıncını 250-280 bar aralığında tutar. Pompa aşınması veya iç kaçak oluştuğunda pompa basıncı tutamaz ve sistem basıncı hızla düşer (150 bar altı kritik). Belirtiler: hidrolik basınç düşük, basınç düşüyor, pompa arızası, yağ pompası bozuk, pompa basmıyor, kepçe kalkmıyor, güç kaybı, titreşim artışı, yağ sıcaklığı düşük (yağ dolaşımı azaldı), yakıt tüketimi arttı. Ayrıca aşınan pompa mekanik titreşim üretir ve motor telafi için daha çok yük çeker. Yağ/hidrolik pompa arızası tespit edildiğinde: 1) Sistem basıncını manometreyle ölçün, 2) Pompa giriş filtresini ve emiş hattını tıkanıklık için kontrol edin, 3) Pompa iç kaçağını (case drain debisi) ölçün, 4) Yağ seviyesini ve viskozitesini doğrulayın, 5) Aşınmışsa pompayı değiştirin. Hydraulic Pump (P/N 56028042), Suction Filter (P/N 56034120).",
        "part_numbers": ["56028042", "56034120"],
        "failure_mode": "pompa arızası, düşük basınç",
    },
    # Elektrik Sistemi
    {
        "id": "lh517-electrical-01",
        "category": "Elektrik Sistemi",
        "title": "LH517 Batarya ve Elektrik Sistemi",
        "content": "LH517 elektrik sistemi 24-48V DC çalışır. Battery (P/N 56020750): asitsiz yedek parça olarak sipariş edilir. Emergency Stop Button (P/N 56013070): YELLOW/RED, IP67 koruma sınıfı, 2 adet. Horn (P/N 56024620): 24-48VDC, 0.8A, 107dB sabit ton. Headlight (P/N 56017520): 1 adet ana far. Elektrik sisteminde arıza tespit edildiğinde önce Emergency Stop butonunu kontrol edin.",
        "part_numbers": ["56020750", "56013070", "56024620", "56017520"],
        "failure_mode": "elektrik arızası",
    },
    {
        "id": "lh517-electrical-02",
        "category": "Elektrik Sistemi",
        "title": "LH517 Uzaktan Kontrol Sistemi",
        "content": "Sandvik LH517 uzaktan kontrol sistemi: Remote Control System Radio (P/N 56045111), Transmitter (P/N 56045293), Interface Remote Control (P/N BG00399273). Uzaktan kontrol arızalarında: 1) Verici pil durumunu kontrol edin, 2) Anten bağlantısını kontrol edin, 3) Frekans çakışmasını kontrol edin. Sistem IP67 koruma sınıfında çalışır.",
        "part_numbers": ["56045111", "56045293", "BG00399273"],
        "failure_mode": "uzaktan kontrol arızası",
    },
    # Yağlama Sistemi
    {
        "id": "lh517-lubrication-01",
        "category": "Yağlama Sistemi",
        "title": "LH517 Merkezi Yağlama Sistemi",
        "content": "Central Lubrication Kit (P/N 56209375): Tüm bağlantı noktalarını otomatik gresleme yapar. Yağlama sıklığı: 8 saatte bir otomatik devreye girer. Manuel kontrol 250 saatte bir yapılmalıdır. Grease nipple tıkanması titreşim ve aşınma artışına neden olur. Covers and Mudguards (P/N 56034355) sökülerek erişim sağlanabilir.",
        "part_numbers": ["56209375", "56034355"],
        "failure_mode": "yağlama yetersizliği",
    },
    # Tartım ve Sensör
    {
        "id": "lh517-sensor-01",
        "category": "Sensör ve Tartım",
        "title": "LH517 Tartım Sistemi ve Sensörler",
        "content": "Weighing System (P/N 56029901): Yük kapasitesi izleme sistemi. Wire Kit (P/N 56015599) ve Balance (P/N 56020567) ile kalibre edilir. Sensor Assembly (P/N 56046804): titreşim ve yük sensörlerini barındırır. Sensör arızası durumunda: 1) Bağlantı kablolarını kontrol edin, 2) Sensör sıfırlama prosedürünü uygulayın, 3) Kalibrasyon değerlerini doğrulayın.",
        "part_numbers": ["56029901", "56015599", "56020567", "56046804"],
        "failure_mode": "sensör arızası, yanlış okuma",
    },
    # Güç Aktarma
    {
        "id": "lh517-powertrain-01",
        "category": "Güç Aktarma",
        "title": "LH517 Devir, Tork ve Yakıt Tüketimi Değerleri",
        "content": "LH517 motoru rölantide 800 d/dk, tam yükte 2100 d/dk devirde çalışır; tepe tork yaklaşık 2300 Nm'dir. Yakıt tüketimi rölantide ~8 L/sa, tam yük ve yokuş koşulunda 45-52 L/sa'e çıkar. Yakıt tüketimi artış nedenleri: hava filtresi tıkanıklığı, sürekli yokuş ve aşırı yük, yetersiz havalandırma nedeniyle düşük oksijen (motor zengin karışıma geçer), enjektör aşınması, düşük lastik basıncı, fren sürtünmesi. Tork düşüklüğü belirtileri: makine yokuşta zorlanıyor, çekiş zayıf; nedenleri: yakıt filtresi tıkanıklığı, turbo kaçağı, enjektör arızası. Belirtiler: yakıt fazla yakıyor, tüketim arttı, devir dalgalanıyor, tork düşük, çekmiyor.",
        "part_numbers": ["56035422", "56021170"],
        "failure_mode": "güç aktarma verimsizliği",
    },
    # Genel Bakım
    {
        "id": "lh517-maintenance-01",
        "category": "Periyodik Bakım",
        "title": "LH517 Bakım Takvimi",
        "content": "Sandvik LH517 bakım aralıkları: 8 saat — yağ seviyeleri, lastik basınç, frenleri kontrol et. 125 saat — filtreler, bağlantı noktaları, gresleme. 250 saat — tüm bushingler, yük sensörü kalibrasyonu, elektrik bağlantıları. 500 saat — motor filtresi değişimi, Liftarm Bushing kontrolü. 1000 saat — hidrolik yağ değişimi, motor incelemesi. Planned maintenance miktarını artırmak downtime'ı %40 azaltır.",
        "part_numbers": [],
        "failure_mode": "genel bakım",
    },
    {
        "id": "lh517-maintenance-02",
        "category": "Periyodik Bakım",
        "title": "LH517 Arıza Tespiti ve Müdahale",
        "content": "LH517 arıza öncelikleri: KIRMIZI (acil durdur) — 105°C üzeri sıcaklık, 220A üzeri akım, 8 mm/s üzeri titreşim. SARI (dikkat) — 95-105°C sıcaklık, 200-220A akım, 5-8 mm/s titreşim. YEŞİL (normal) — tüm değerler normal aralıkta. Müdahale süresi hedefi: KIRMIZI için 15 dakika, SARI için 4 saat içinde bakım planlanmalıdır.",
        "part_numbers": [],
        "failure_mode": "genel arıza müdahalesi",
    },
    {
        "id": "lh517-fire-01",
        "category": "Güvenlik",
        "title": "LH517 Yangın Söndürme ve Güvenlik Sistemi",
        "content": "Fire Extinguishing System (P/N 56205923): Otomatik yangın söndürme sistemi. Motor bölmesindeki sıcaklık sensörü 200°C'yi aştığında otomatik devreye girer. Bakım aralığı 12 aydır. Emergency Stop (P/N 56013070, IP67, YELLOW/RED) her 500 saatte test edilmelidir. Service Railings (P/N 56039605) bakım esnasında mutlaka kullanılmalıdır.",
        "part_numbers": ["56205923", "56013070", "56039605"],
        "failure_mode": "yangın, güvenlik sistemi",
    },
    {
        "id": "lh517-brake-01",
        "category": "Fren Sistemi",
        "title": "LH517 Fren Sistemi ve Aşırı Isınma",
        "content": "LH517 SAHR (yay uygulamalı, hidrolik boşaltmalı) ıslak disk fren sistemi kullanır. Normal fren yüzey sıcaklığı 120°C altındadır; 180°C üzeri aşırı ısınma, balata sürtmesi (fren dragı) veya soğutma yağı yetersizliğini gösterir. Belirtiler: fren tutmuyor/zayıf, fren kokusu, yanık kokusu, makine yavaşlıyor/sürtüyor, fren sıcak, duruş mesafesi uzadı, yokuşta kayma. Yeraltında fren arızası ölümcül İSG riskidir — üretici sınırının altında aşınmış balatayla çalıştırma yasaktır. Fren aşırı ısınmasında: 1) Fren soğutma yağı seviyesi ve sıcaklığını kontrol edin, 2) Balata aşınmasını ölçün (min. kalınlık), 3) Fren boşaltma basıncını doğrulayın, 4) Park freni ayarını kontrol edin. Brake Disc Kit (P/N 56042100), Brake Cooling Pump (P/N 56033120).",
        "part_numbers": ["56042100", "56033120"],
        "failure_mode": "fren aşırı ısınması, fren arızası",
    },
    {
        "id": "lh517-transmission-01",
        "category": "Güç Aktarma",
        "title": "LH517 Transmisyon / Şanzıman Arızası",
        "content": "LH517 güç aktarma organında (tork konvertör + şanzıman) dişli ve rulman aşınması yüksek titreşim ve şanzıman yağ sıcaklığı artışı üretir. Normal şanzıman yağ sıcaklığı 80-110°C; 120°C üzeri ve titreşim artışı iç aşınmayı gösterir. Belirtiler: vites atıyor/kaçırıyor, güç aktarmıyor, titreşim/gürültü, şanzıman sıcak, hızlanma zayıf, sarsıntılı hareket, metalik ses. Transmisyon arızasında: 1) Şanzıman yağı seviyesi/rengini kontrol edin (metal talaşı), 2) Yağ sıcaklığı ve soğutucusunu kontrol edin, 3) Tork konvertör basıncını ölçün, 4) Yağ ve filtreyi 1000 saatte değiştirin. Transmission Assembly (P/N 56048800), Oil Filter (P/N 56034120).",
        "part_numbers": ["56048800", "56034120"],
        "failure_mode": "transmisyon arızası, dişli aşınması",
    },
    {
        "id": "lh517-cooling-01",
        "category": "Soğutma Sistemi",
        "title": "LH517 Soğutma Sistemi ve Radyatör",
        "content": "LH517 motor soğutma sistemi radyatör, fan, su pompası ve termostattan oluşur. Normal soğutma sıvısı sıcaklığı 70-90°C; radyatör tıkanıklığı, fan arızası, düşük soğutma sıvısı veya termostat arızasında motor sıcaklığı sürekli yükselir. Belirtiler: motor ısınıyor/hararet yapıyor, sıcaklık düşmüyor, soğutma sıvısı eksiliyor, fan dönmüyor, radyatör tıkalı/kirli, buhar. Motor iç arızasından farkı: akım normaldir, sorun soğutma tarafındadır. Soğutma sistemi arızasında: 1) Soğutma sıvısı seviyesi ve kaçak kontrolü, 2) Radyatör peteklerini basınçlı hava ile temizleyin, 3) Fan ve kayışını kontrol edin, 4) Termostat ve su pompasını test edin. Radiator Assembly (P/N 56035400), Cooling Fan (P/N 56035420), Water Pump (P/N 56035440).",
        "part_numbers": ["56035400", "56035420", "56035440"],
        "failure_mode": "soğutma arızası, radyatör tıkanıklığı",
    },
]


# ── VEKTÖRLENMİŞ ÖRNEK (sunumla tutarlılık) ───────────────────────────────────
# Sunumda "üreticinin tam servis manuelini henüz vektörlemedik; bu İP-8 (final)
# işidir, altyapı hazır ama tam kapasite değil" diyoruz. Bu yüzden bilgi tabanının
# TAMAMINI değil, yalnızca temsili bir ÖRNEĞİNİ Qdrant'a gömüyoruz. Böylece
# yalnız bu arızalara güvenilir cevap gelir; diğer arıza sorularında sistem
# dürüstçe "bulunamadı" der (jüri "tüm arızaları nasıl önceden gömdünüz?" demez).
# Final için: AKTIF_IDS'e yeni doküman id'leri eklemek yeterli.
AKTIF_IDS = {
    "lh517-hydraulic-pump-01",   # Yağ/Hidrolik Pompa (sunumdaki RAG örneği — basınç)
    "lh517-motor-02",            # Motor Akım Limitleri (aşırı akım — benzersiz konu)
}
# Not: benzersiz-konulu iki doküman seçildi. Titreşim (rulman/transmisyon/enjektör)
# ve sıcaklık (ısınma/fren/soğutma) konuları küme oluşturduğundan, o kümeden bir
# doküman tutmak birden çok arızaya sızardı. Basınç ve akım tek arızaya ait → temiz.


def _aktif_kb() -> List[Dict]:
    return [d for d in KNOWLEDGE_BASE if d["id"] in AKTIF_IDS]


def index_knowledge():
    """Bilgi tabanının AKTİF (vektörlenmiş örnek) kısmını Qdrant'a yükle."""
    global _indexed
    _ensure_collection()
    q = _get_qdrant()
    enc = _get_encoder()

    kb = _aktif_kb()
    # Aktif set değişince sayı aynı kalıp içerik farklı olabilir (2 eski ≠ 2 yeni);
    # sayıya güvenmeyip her açılışta koleksiyonu tazeliyoruz (yalnız birkaç blok,
    # saniyeler sürer). _indexed bayrağı süreç içinde tekrar yüklemeyi önler.
    q.delete_collection(COLLECTION)
    _ensure_collection()

    points = []
    for i, doc in enumerate(kb):
        # E5 kuralı: doküman tarafı "passage: " önekiyle kodlanır
        text = f"passage: {doc['title']}: {doc['content']}"
        vector = enc.encode(text).tolist()
        points.append(PointStruct(
            id=i + 1,
            vector=vector,
            payload={
                "id":          doc["id"],
                "category":    doc["category"],
                "title":       doc["title"],
                "content":     doc["content"],
                "part_numbers": doc["part_numbers"],
                "failure_mode": doc["failure_mode"],
            }
        ))

    q.upsert(collection_name=COLLECTION, points=points)
    _indexed = True
    print(f"RAG: {len(points)} bilgi bloğu Qdrant'a yüklendi.")


def query(question: str, limit: int = 3) -> List[Dict]:
    """Soruya en alakalı bilgi bloklarını döndür."""
    if not _indexed:
        index_knowledge()

    enc = _get_encoder()
    q   = _get_qdrant()

    # SOHBET KAPISI (anlamsal, kelime listesi DEĞİL): sorgu, selamlaşma
    # örneklerinin anlam merkezine 0.76'dan yakınsa sohbettir → sonuç yok.
    import numpy as _np
    global _greet_centroid
    if _greet_centroid is None:
        ornekler = ["selam", "merhaba", "naber", "nasılsın", "günaydın",
                    "iyi akşamlar", "ne haber dostum", "hava bugün çok güzel"]
        vecs = enc.encode([f"query: {o}" for o in ornekler])
        _greet_centroid = _np.mean(vecs, axis=0)
        _greet_centroid /= _np.linalg.norm(_greet_centroid)
    qv = _np.asarray(enc.encode(f"query: {question}"), dtype=float)
    qv /= _np.linalg.norm(qv)
    if float(qv @ _greet_centroid) >= GREET_ESIK:
        return []

    # Kısa sorgular (1-2 kelime, örn. "hararet") tek başına yeterli anlam
    # taşımaz; arıza bağlamı eklenerek aranır
    kisa = len(question.split()) <= 2
    arama = f"makine arıza belirtisi: {question}" if kisa else question
    vector = enc.encode(f"query: {arama}").tolist()
    response = q.query_points(
        collection_name=COLLECTION,
        query=vector,
        limit=limit,
        # Eşik 0.50: yalnız güçlü/gerçek eşleşmeler geçsin; zayıf komşu-konu
        # sızıntıları (ör. enjektör→pompa %47) elensin → "bulunamadı" dürüst kalır.
        score_threshold=0.50,
    )

    return [
        {
            "score":        round(r.score, 3),
            "category":     r.payload["category"],
            "title":        r.payload["title"],
            "content":      r.payload["content"],
            "part_numbers": r.payload["part_numbers"],
        }
        for r in response.points
    ]


def query_by_anomaly(equipment_type: str, anomaly_description: str) -> Dict:
    """Anomali açıklamasına göre teknik öneri üret."""
    question = f"{equipment_type} {anomaly_description}"
    results  = query(question, limit=2)

    if not results:
        return {
            "soru":    question,
            "sonuclar": [],
            "ozet":    "Bilgi tabanında ilgili kayıt bulunamadı.",
        }

    ozet_parts = []
    for r in results:
        ozet_parts.append(f"[{r['category']}] {r['title']}")

    return {
        "soru":    question,
        "sonuclar": results,
        "ozet":    f"İlgili {len(results)} teknik doküman bulundu: " + " | ".join(ozet_parts),
    }
