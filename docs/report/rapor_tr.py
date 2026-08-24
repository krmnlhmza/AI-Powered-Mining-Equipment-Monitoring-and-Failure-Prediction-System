# -*- coding: utf-8 -*-
"""ÇankaYazılım — Teknik ve Ticari Rapor (Türkçe)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _rapor_ortak import (Rapor, ARAYUZ, SEMA, PRIMARY, ACCENT, RED, GREEN,
                          MUTED, GENISLIK)

GITHUB = "github.com/krmnlhmza/AI-Powered-Mining-Equipment-Monitoring-and-Failure-Prediction-System"

pdf = Rapor("Yapay Zeka Destekli Maden Ekipmanı İzleme ve Arıza Tahmin Sistemi",
            "ÇankaYazılım · Teknik ve Ticari Rapor")

pdf.kapak(
    baslik="Yapay Zeka Destekli Maden Ekipmanı\nİzleme ve Arıza Tahmin Sistemi",
    altbaslik="Ağır iş makineleri için dijital ikiz tabanlı kestirimci bakım platformu",
    etiket="Teknik ve Ticari Rapor  ·  Çalışan prototip  ·  Uçtan uca açık kaynak teknoloji yığını\n"
           "TEKNOFEST 2026 Maden Teknolojileri Yarışması Yarı Finalisti",
    yazar_blok="Muhammed Hamza KARAMANLI\nTakım Kaptanı ve Proje Yöneticisi",
    tarih="Ağustos 2026",
    iletisim=f"hamzakaramanli33@gmail.com  ·  hamzakaramanli2011@outlook.com\n{GITHUB}")

pdf.add_page()

# ─────────────────────────── 1 ───────────────────────────
pdf.h1("1", "Yönetici Özeti")
pdf.p("Yeraltı madenciliğinde ağır iş makineleri operasyonun can damarıdır; ancak bu makinelerin sağlığı "
"bugün hâlâ büyük ölçüde reaktif yönetilmektedir: arıza gerçekleştikten sonra müdahale edilir. Bunun üç "
"somut bedeli vardır — yüksek bakım maliyeti, analiz edilmeden kaybolan sensör verisi ve ekipman kaynaklı "
"ölümcül iş kazaları.")
pdf.p("ÇankaYazılım olarak geliştirdiğimiz sistem, ağır iş makinelerini bir dijital ikiz üzerinde sürekli "
"izleyen, arızayı gerçekleşmeden önce tahmin eden ve operatöre çözümü anında sunan bütünleşik bir "
"kestirimci bakım platformudur. Piyasadaki pasif izleme panellerinden farkı, veriyi yalnızca göstermek "
"yerine bir karara ve otomatik aksiyona (bakım iş emri, rapor, bildirim) dönüştürmesidir.")
pdf.p("Sistem dört yapay zeka bileşeninin birlikte çalıştığı hibrit bir mimariye dayanır: anlık anomali "
"tespiti için Isolation Forest, kalan faydalı ömür (RUL) tahmini için LSTM, servis dokümanlarından anlık "
"çözüm üreten RAG tabanlı teknik asistan ve kritik olaylarda bildirim/rapor zincirini başlatan n8n "
"otomasyonu. Tüm teknoloji yığını açık kaynak bileşenlerden oluşur; yazılım lisans maliyeti bulunmaz ve "
"sistem tamamen kurum içi (on-premise) çalışabildiği için veri işletmenin dışına çıkmaz.")
pdf.p("Prototip uçtan uca çalışır durumdadır. Yapılan doğrulama testlerinde, normal çalışma koşullarında "
"üretilen 2.250 sensör okumasında hiç yanlış alarm üretilmemiş; sekiz farklı arıza tipiyle oluşturulan "
"480 arıza olayının tamamı tespit edilmiştir.")
pdf.kpi([("%0,00", "Normal çalışmada\nyanlış alarm oranı"),
         ("%100", "Arıza olaylarında\ntespit oranı"),
         ("0 ₺", "Yazılım lisans\nmaliyeti"),
         ("8", "Doğrulanmış arıza\nsenaryosu")])
pdf.kutu("Bu rapor kime hitap ediyor?",
"Maden işletmeleri ve bakım/İSG birimleri, ağır iş makinesi servis sağlayıcıları, endüstriyel dijital "
"dönüşüm ve Endüstri 4.0 yatırımcıları ile teknoloji iş birliği arayan kurumlar.")

# ─────────────────────────── 2 ───────────────────────────
pdf.h1("2", "Problem Tanımı")
pdf.p("Yeraltı maden işletmeleri; derinleşen rezervler, düşen cevher tenörü ve zorlu çalışma koşulları "
"altında üretkenliği koruyabilmek için hızla dijitalleşmek zorundadır. Sahadaki SCADA panelleri sensör "
"verisini yalnızca ekrana yansıtır; insan gözüyle fark edilemeyecek mikro titreşim ve akım değişimleri "
"analiz edilmediği için yaklaşan arızalar önceden görülemez. Problem üç boyutta somutlaşır.")

pdf.h2("2.1  Bakım maliyeti")
pdf.p("Madencilik gibi ağır sanayi operasyonlarında bakım giderleri, toplam üretim maliyetlerinin "
"%60'ına kadar çıkabilmektedir (Savolainen & Urbani, 2021). Reaktif modelde asıl tamir çoğu zaman kısa "
"sürse de, arızanın geç fark edilmesi ve yedek parça bekleme süreçleri yüzünden üretim duruşları saatlere, "
"hatta günlere uzar; bu da planlı bir bakıma kıyasla operasyonu çok daha maliyetli hâle getirir.")

pdf.h2("2.2  Verinin israfı")
pdf.p("Otonom bir iş makinesi üzerindeki yaklaşık 180 sensörle günde 2,5 TB veri üretmektedir; ancak bu "
"verinin yalnızca %1'i karar süreçlerinde kullanılabilmektedir (Don vd., 2025). Geri kalanı, sistemlerin "
"birbiriyle konuşamaması nedeniyle analiz edilmeden kaybolur. Sahada eksik olan sensör ya da veri değildir; "
"bu veriyi zamanında anlamlı bir karara dönüştürecek yapay zeka katmanıdır.")

pdf.h2("2.3  İş güvenliği")
pdf.p("Yeraltı madenciliğinde en ağır kazaların %40'tan fazlası bir iş makinesine çarpma veya sıkışmadan, "
"ölümlerin %43'ü ise yükleyici ve kamyon gibi ağır nakil ekipmanından kaynaklanmaktadır (CDC/NIOSH). "
"Dolayısıyla bir ekipman arızası yalnızca ekonomik değil, aynı zamanda bir can güvenliği sorunudur ve "
"fiziksel bir kazaya dönüşmeden önce yakalanmalıdır.")
pdf.kutu("Gerçek vaka — MSHA Nihai Raporu, 22 Şubat 2021",
"Bir yeraltı ocağında, fren balataları üretici sınırının altında aşınmış ve bakımı ihmal edilmiş bir maden "
"lokomotifinin freni tutmayınca 26 yaşındaki operatör hayatını kaybetti. Resmî rapor kök nedeni \"arızalı "
"fren sistemiyle çalıştırma ve olağanın ötesinde ihmal\" olarak belirledi. Bu vaka, izlenmeyen ekipman "
"aşınmasının yalnızca ekonomik değil ölümcül olduğunu; kestirimci bakımın neden hayati olduğunu gösterir.",
RED)

# ─────────────────────────── 3 ───────────────────────────
pdf.h1("3", "Literatür ve Mevcut Durum")
pdf.p("Proje kapsamında anomali tespiti, kalan ömür tahmini, RAG ve dijital ikiz konularında on ikiden "
"fazla akademik çalışma incelenmiştir. Literatürde bu bileşenlerin her biri ayrı ayrı olgunlaşmıştır; "
"ancak dördünü marka-bağımsız, çift yönlü ve tek bir platformda birleştiren bir çalışma bulunmamaktadır. "
"Projemizin doldurduğu boşluk budur.")
pdf.tablo(
    ["#", "Çalışma (Yazar, Yıl & Başlık)", "Kaynak", "Katkısı / bulgusu"],
    [
    ["1", "Savolainen, J. & Urbani, M. (2021). Maintenance optimization for a multi-unit system with digital twin simulation.",
     "Journal of Intelligent Manufacturing, 32(7), 1953–1973.",
     "Madende bakım, üretim maliyetinin %60'ına kadar; dijital ikizle filo optimizasyonu."],
    ["2", "Don, M. G., Wanasinghe, T. R., Gosine, R. G. & Warrian, P. J. (2025). Digital Twins and Enabling Technology Applications in Mining.",
     "IEEE Access, 13, 6945–6963.",
     "Madende dijital ikiz trendleri; araç günde 2,5 TB üretir, %1'i kullanılır."],
    ["3", "van Eyk, L. & Heyns, P. S. (2025). A framework to define, design and construct digital twins in the mining industry.",
     "Computers & Industrial Engineering, 200, 110805.",
     "Çift yönlü veri akışı olmadan bir sistem gerçek 'ikiz' sayılamaz."],
    ["4", "Kuş, Ş., Tatar, F. & Toprakal, E. (2023). Raylı Sistemlerde Dijital İkiz.",
     "Orclever Proceedings of Research and Development, 3(1), 104–114.",
     "Raylı sistemlerde dijital ikiz (BIM) uygulaması ve maliyet tasarrufu."],
    ["5", "Liu, F. T., Ting, K. M. & Zhou, Z.-H. (2008). Isolation Forest.",
     "2008 Eighth IEEE Int. Conf. on Data Mining (ICDM), 413–422.",
     "Isolation Forest — anomali tespitinin temel algoritması."],
    ["6", "Hochreiter, S. & Schmidhuber, J. (1997). Long Short-Term Memory.",
     "Neural Computation, 9(8), 1735–1780.",
     "LSTM — zaman serisi ve kalan ömür (RUL) tahmininin temel mimarisi."],
    ["7", "Neupane, D., Bouadjenek, M. R., Dazeley, R. & Aryal, S. (2025). Data-driven machinery fault diagnosis: A comprehensive review.",
     "Neurocomputing, 627, 129588.",
     "Veriye dayalı arıza teşhisinin kapsamlı haritası."],
    ["8", "Muratbakeev, E., Kozhubaev, Y., Novak, D., Ershov, R. & Wei, Z. (2025). Monitoring and Diagnostics of Mining Electromechanical Equipment Based on Machine Learning.",
     "Symmetry, 17(9), 1548.",
     "Doğrudan maden ekipmanına makine öğrenmesiyle teşhis."],
    ["9", "Bharatheedasan, K., Maity, T., Kumaraswamidhas, L. A. & Durairaj, M. (2025). Enhanced fault diagnosis and RUL prediction of rolling bearings using a hybrid MLP–LSTM network model.",
     "Alexandria Engineering Journal, 115, 355–369.",
     "Hibrit yaklaşımın (bizimki gibi) yüksek başarımı."],
    ["10", "Lewis, P., Perez, E., Piktus, A., Petroni, F. vd. (2020). Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.",
     "Advances in Neural Information Processing Systems (NeurIPS), 33, 9459–9474.",
     "RAG — teknik asistan katmanımızın temel makalesi."],
    ["11", "Chen, L.-C., Pardeshi, M. S., Liao, Y.-X. & Pai, K.-C. (2025). Application of retrieval-augmented generation for interactive industrial knowledge management via a large language model.",
     "Computer Standards & Interfaces, 94, 103995.",
     "Endüstride RAG ile teknik dokümana anlamsal erişim."],
    ["12", "Cacciuttolo, C., Atencio, E., Komarizadehasl, S. & Lozano-Galant, J. A. (2024). IoT LoRaWAN-Based Wireless Sensors Network for Underground Mine Monitoring.",
     "Sensors, 24(21), 6971.",
     "Yer altı kablosuz sensör ağı (WSN) altyapısı."],
    ],
    [8, 66, 42, 64])
pdf.p("Tablo 1. Literatürdeki başlıca çalışmalar ve projemizin doldurduğu boşluğun karşılaştırması.", 7.4)

# ─────────────────────────── 4 ───────────────────────────
pdf.h1("4", "Çözüm Yaklaşımı")
pdf.p("Sektördeki mevcut sistemlerin çoğu, sensör verisini yalnızca ekrana yansıtan pasif izleme "
"panelleridir; literatürde bu tür sistemler \"Dijital Gölge\" olarak adlandırılır (van Eyk & Heyns, 2025), "
"çünkü veriyi tek yönlü gösterir ama ondan bir karar üretmezler. Çözümümüz tam bu noktada ayrışır: veriyi "
"işleyip anlamlı bir karara dönüştürür ve bu kararla otomatik bir aksiyon zincirini insan müdahalesi "
"olmadan başlatır. İzlemekten otonom aksiyona geçen bu kapalı karar döngüsü, sistemi pasif bir gösterge "
"panosunun ötesine taşıyan gerçek bir dijital ikiz yaklaşımıdır.")

pdf.h2("4.1  Problemden çözüme eşleştirme")
pdf.tablo(["Problem", "Çözüm bileşenimiz", "Sonuç"],
    [["Reaktif bakım: yüksek maliyet ve plansız duruş",
      "Isolation Forest (anomali) + LSTM (kalan ömür)",
      "Arıza günler öncesinden yakalanır → kestirimci bakım"],
     ["Sensör verisinin %99'u analiz edilmeden kayboluyor",
      "Dijital ikiz + yapay zeka karar katmanı",
      "Ham veri anlık, otonom karara dönüşür"],
     ["Bilgiye geç erişim → uzun onarım süresi (MTTR)",
      "RAG tabanlı teknik asistan",
      "Manuelden saniyeler içinde çözüm adımı"],
     ["Ekipman kaynaklı iş güvenliği riski",
      "Anomali / erken uyarı katmanı",
      "Kaza fiziksel hâle gelmeden önlenir"]],
    [60, 58, 62])
pdf.p("Tablo 2. Tanımlanan problemlerin çözüm bileşenlerimizle eşleştirilmesi ve elde edilen sonuçlar.", 7.4)

pdf.h2("4.2  Geleneksel izleme ile karşılaştırma")
pdf.tablo(["Özellik", "Geleneksel izleme (Dijital Gölge)", "ÇankaYazılım (Dijital İkiz)"],
    [["Veri akışı", "Tek yönlü — veriyi yalnızca ekranda gösterir", "Veri → karar → otomatik aksiyon"],
     ["Karar", "İnsan yorumlar, elle müdahale", "Otomatik anomali tespiti + kritiklik kararı"],
     ["Yapay zeka", "Sabit eşik / tek model", "Hibrit: Isolation Forest + LSTM"],
     ["Teknik destek", "Ham veri veya hata kodu sunar", "RAG asistan: manuelden anlık çözüm"],
     ["Aksiyon", "Pasif alarm; operatör arar", "Otomatik iş emri + PDF rapor + bildirim"]],
    [34, 73, 73])
pdf.p("Tablo 3. Geleneksel izleme ile çözümümüzün karşılaştırması.", 7.4)

# ─────────────────────────── 5 ───────────────────────────
pdf.h1("5", "Sistem Mimarisi")
pdf.p("Sistem, sahadan arayüze uzanan beş katmanlı, mikroservis tabanlı bir mimari üzerine kuruludur. "
"Tüm servisler Docker ve Docker Compose ile paketlenmiştir; böylece yerel sunucuda (edge) veya bulutta "
"taşınabilir şekilde çalışır. Her bileşen bağımsız olarak güncellenebilir veya değiştirilebilir.")
pdf.gorsel(os.path.join(SEMA, "mimari.png"),
           "Şekil 1. Beş katmanlı mikroservis mimarisi: veri toplama, mesajlaşma, veri yönetimi, "
           "backend & yapay zeka ve arayüz/otomasyon katmanları.", genislik=132)
pdf.madde([
"Veri toplama (saha): Sıcaklık (°C), titreşim (mm/s), basınç (bar), akım (A), hız (km/h), devir (d/dk), "
"tork (Nm) ve yakıt (L/sa) verileri; sahada yaygın olan Modbus, MQTT ve OPC-UA adaptörleri üzerinden "
"okunur ve ortak bir JSON şemasına normalize edilir.",
"Mesajlaşma: Normalize edilmiş her okuma, Eclipse Mosquitto MQTT broker üzerinden gerçek zamanlı "
"yayınlanır. MQTT tercih edilmiştir; düşük bant genişliği tüketir, gecikmesi çok düşüktür ve QoS "
"mekanizması sayesinde bağlantının koptuğu yer altı koşullarında dahi mesaj güvenilirliğini destekler.",
"Veri yönetimi: Abone servis, gelen her mesajı zaman serisi sorguları için TimescaleDB'ye kalıcı olarak "
"yazar, canlı arayüzün okuduğu son durumu Redis'e koyar ve anomali tespitini tetikler. Teknik "
"dokümanların vektör temsilleri Qdrant'ta tutulur.",
"Backend ve yapay zeka: Asenkron FastAPI backend; anomali, RUL ve RAG servislerini REST uçları üzerinden "
"yönetir.",
"Arayüz ve otomasyon: Tarayıcı üzerinde çalışan gerçek zamanlı izleme panosu, bileşen düzeyinde 2B dijital "
"ikiz gösterimi, teknik asistan arayüzü ve kritik anomalide bildirim zincirini başlatan n8n otomasyonu.",
])
pdf.h2("5.1  Teknoloji yığını")
pdf.tablo(["Katman", "Bileşen", "Rol"],
    [["Çalışma zamanı", "Python 3.12, FastAPI, Uvicorn", "Asenkron REST servisleri"],
     ["Zaman serisi", "TimescaleDB (PostgreSQL eklentisi)", "Kalıcı sensör geçmişi, hızlı zaman sorguları"],
     ["Önbellek", "Redis", "Canlı son durum; arayüz diske yük bindirmez"],
     ["Vektör veritabanı", "Qdrant", "Servis dokümanlarının anlamsal araması"],
     ["Mesajlaşma", "Eclipse Mosquitto (MQTT 3.1.1)", "Saha → sistem gerçek zamanlı veri hattı"],
     ["Makine öğrenmesi", "scikit-learn, PyTorch", "Isolation Forest, LSTM"],
     ["Otomasyon", "n8n", "Bildirim, PDF rapor ve log zinciri"],
     ["Paketleme", "Docker, Docker Compose", "Taşınabilir, tek komutla kurulum"]],
    [34, 56, 90])
pdf.p("Tablo 4. Kullanılan teknoloji yığını. Tüm bileşenler açık kaynak veya kaynağı açık (fair-code) "
"lisanslıdır; kurum içi kullanımda yazılım lisans ücreti bulunmamaktadır.", 7.4)

# ─────────────────────────── 6 ───────────────────────────
pdf.h1("6", "Yapay Zeka Katmanı")

pdf.h2("6.1  Isolation Forest — anlık anomali tespiti")
pdf.p("Her ekipmandan gelen çok değişkenli sensör okuması (sıcaklık, titreşim, basınç, akım ve hız) "
"denetimsiz Isolation Forest algoritmasıyla değerlendirilir. Algoritma veriyi rastgele bölerek çok sayıda "
"karar ağacı kurar; normal veriler ağaçta derinlere inerken, diğerlerinden farklı davranan anormal noktalar "
"çok daha az adımda izole edilir. Model her makinenin normal çalışma karakteristiğini önceden öğrenir ve bu "
"profilden sapan mikro değişimleri anlık olarak yakalar.")
pdf.madde([
"Her ekipmanın kendi modeli vardır; bir yükleyicinin \"normali\" ile bir kamyonunki aynı değildir.",
"Üretilen ham skor, eğitimde ayrılan bir doğrulama kümesi üzerinden 0–1 aralığına kalibre edilir. "
"Sağlıklı makine tipik olarak 0,10–0,30 bandında kalır.",
"Skor 0,60'ı aştığında arayüz uyarı durumuna geçer; 0,70'i aşan kritik anomaliler otomasyon zincirini "
"tetikler.",
"Kararlılık için ardışık teyit kuralı uygulanır: anomali ilan edilmeden önce art arda en az üç okumanın "
"eşiği aşması gerekir. Böylece tekil gürültü sıçramaları elenir, gerçek arızalar ise saniyeler içinde "
"doğrulanır.",
])

pdf.h2("6.2  LSTM — kalan faydalı ömür (RUL) tahmini")
pdf.p("Ekipmanın ne zaman arızalanacağını öngörmek için derin öğrenme tabanlı bir LSTM regresörü "
"eğitilmiştir. Model, her ekipmanın son 20 sensör okumasından oluşan bir zaman penceresini (5 özellik × "
"20 adım) girdi alır ve geçmiş telemetrideki yıpranma (degradasyon) trendlerini öğrenerek normalize bir "
"sağlık/kalan ömür skoru üretir. Bu skor saat cinsine ölçeklenir ve eşiklerle karara bağlanır: kalan ömür "
"24 saatin altına düştüğünde planlı bakım uyarısı, 8 saatin altına düştüğünde acil bakım iş emri "
"oluşturulur.")
pdf.p("Model, sağlıklı durumdan arızaya uzanan (run-to-failure) yüzlerce yıpranma eğrisiyle eğitilmiştir. "
"Ayrıca eşik-farkındalıklı hibrit bir düzeltme uygulanır: bir sensör kritik eşiğe yaklaştığında, fizik "
"tabanlı bir üst sınır ile model tahmininin küçüğü alınır. Böylece sağlıklı makinede model dürüst kalırken, "
"ani gelişen arızalarda kalan ömür gerçekçi biçimde kısalır.")

pdf.h2("6.3  RAG tabanlı teknik asistan")
pdf.p("Operatörün arıza anında hızlı ve güvenilir teknik destek alabilmesi için, üreticilerin bakım "
"manuelleri anlamlı parçalara ayrılır ve bir gömme (embedding) modeliyle sayısal vektörlere dönüştürülerek "
"Qdrant vektör veritabanında saklanır. Operatör doğal dille bir soru sorduğunda, sorusu da aynı modelle "
"vektöre çevrilir ve veritabanındaki anlamca en yakın doküman bölümleri kosinüs benzerliğiyle bulunup çözüm "
"adımı olarak ekrana getirilir. Bu sayede teknik servise bağımlılık azalır, onarım süresi (MTTR) kısalır.")
pdf.kutu("Doğruluk ilkesi — halüsinasyon yok",
"Sistem, benzerlik eşiğinin altında kalan sorularda cevap uydurmaz; \"güvenilir eşleşme bulunamadı\" yanıtı "
"verir ve kapsamını açıkça belirtir. Endüstriyel bakımda yanlış bir talimat, cevapsızlıktan daha "
"tehlikelidir. Sistem yalnızca kaynak dokümana dayanan yanıt üretir.", PRIMARY)
pdf.p("Gömme modeli tamamen yerel çalışır; sorgular ve dokümanlar hiçbir dış servise gönderilmez. Mevcut "
"sürüm açık kaynak bir çok dilli gömme modeli kullanmaktadır. Yol haritasında, daha yüksek erişim başarımı "
"veren güncel açık kaynak modellere geçiş planlanmaktadır; bu geçiş de ek lisans maliyeti doğurmaz.")

pdf.h2("6.4  n8n ile otonom bildirim ve raporlama")
pdf.p("Bir kritik anomali tespit edildiğinde sistem, n8n otomasyon platformunun webhook'una bildirim "
"gönderir. n8n, skoru 0,70'i aşan kritik olayları bir filtreden geçirir ve insan müdahalesi olmadan üç "
"paralel işi otomatik başlatır: bakım ekibine anlık bildirim (e-posta/Slack), olayın PDF raporunun "
"üretilmesi ve sistem log'una kayıt. Böylece tespit anından bakım ekibinin haberdar olmasına kadar geçen "
"süre saniyelere iner.")
pdf.gorsel(os.path.join(SEMA, "n8n_akis.png"),
           "Şekil 2. Otonom bildirim ve raporlama iş akışı: kritik anomaliler filtrelenir; bildirim, "
           "PDF rapor ve sistem log işleri paralel olarak tetiklenir.", genislik=160)

# ─────────────────────────── 7 ───────────────────────────
pdf.h1("7", "Veri Katmanı ve Dijital İkiz Simülatörü")
pdf.p("Yeraltı maden makinelerinin gerçek sensör telemetrisi üreticiler tarafından tescilli tutulmakta ve "
"dışarıya paylaşılmamaktadır. Bu nedenle geliştirme ve doğrulama aşamasında, makinenin fiziğini modelleyen "
"bir dijital ikiz simülatörü geliştirilmiştir. Simülatör rastgele sayı üretmez; üreticinin resmî teknik "
"dokümanlarındaki gerçek çalışma aralıklarını esas alır ve sensörler arasındaki fiziksel bağıntıları "
"korur.")
pdf.madde([
"Ekipman profili: Her makinenin sensör aralıkları üreticinin teknik dokümanından alınır (örn. bir yeraltı "
"yükleyicisi için sıcaklık 72–88 °C, devir 800–2100 d/dk, hidrolik basınç 250–280 bar, akım 150–195 A).",
"Operasyon döngüsü: Makine gerçek bir iş çevriminde dolaşır — rölanti, yığına yaklaşma, kepçe doldurma, "
"yüklü taşıma, boşaltma, boş dönüş. Ayrıca kötü/taşlık yol, yokuş yukarı yüklü gibi koşullar elle "
"seçilebilir.",
"Fiziksel korelasyon: Sensörler bağımsız değildir. Yük artarsa sıcaklık, akım ve titreşim birlikte artar; "
"devir yükseldikçe titreşim ve yakıt tüketimi artar; yokuş aşağı inişte motor freni devreye girer, tork "
"düşer ve makine soğur; hidrolik aksiyonda basınç anlık yükselir.",
"Yıpranma ve gürültü: Çalışma saatleri biriktikçe yıpranma seviyesi artar ve yıpranmış rulmanlar titreşim "
"ile sıcaklık tabanını yukarı kaydırır. Her ölçüme, gerçek sensör davranışını taklit eden kontrollü Gauss "
"gürültüsü eklenir.",
])
pdf.p("Simülatör, gerçek saha hattının aynısını besler: üretilen veri MQTT üzerinden yayınlanır ve "
"sistemin geri kalanı bunu gerçek bir sensörden gelmiş gibi işler. Bu sayede sahaya geçişte mimaride "
"değişiklik gerekmez; simülatörün yerini gerçek sensör hattı alır.")
pdf.gorsel(os.path.join(ARAYUZ, "simulator-kosullar.png"),
           "Şekil 3. Dijital ikiz simülatörünün fiziksel çalışma koşulu senaryoları.", genislik=150)

# ─────────────────────────── 8 ───────────────────────────
pdf.h1("8", "Doğrulama ve Test Sonuçları")
pdf.p("Sistem, hem yanlış alarm üretmemesi hem de gerçek arızaları kaçırmaması bakımından ölçülmüştür. "
"Aşağıdaki sonuçlar, üç ekipman ve tüm çalışma koşulları üzerinde yürütülen otomatik testlerden elde "
"edilmiştir.")
pdf.tablo(["Test", "Kapsam", "Sonuç"],
    [["Normal çalışmada yanlış alarm",
      "3 ekipman × tüm çalışma koşulları, toplam 2.250 sensör okuması",
      "0 yanlış alarm (%0,00)"],
     ["Arıza tespiti (olay bazlı)",
      "8 arıza tipi × 3 ekipman × 20 tekrar = 480 arıza olayı",
      "480 olayın tamamı tespit edildi (%100)"],
     ["Uçtan uca akış",
      "Simülatör → MQTT → veri tabanı → anomali → RUL → asistan",
      "98.000+ okuma kesintisiz işlendi"],
     ["Tespit gecikmesi",
      "3 saniyelik yayın aralığı, üç ardışık teyit kuralı",
      "Arıza başlangıcından bildirime ~10 saniye"]],
    [46, 74, 60])
pdf.p("Tablo 5. Doğrulama testleri ve sonuçları.", 7.4)
pdf.kutu("Dürüstlük notu",
"Bu sonuçlar, üreticinin teknik değerlerine dayalı fiziksel simülasyon verisi üzerinde elde edilmiştir; "
"gerçek saha verisi değildir. Gerçek bir kurulumda modellerin sahadan toplanan veriyle yeniden eğitilmesi "
"ve doğrulanması gerekir. Mimari, bu yeniden eğitimi tek bir komutla yapacak şekilde tasarlanmıştır.",
ACCENT)

pdf.h2("8.1  Doğrulanan arıza senaryoları")
pdf.p("Sekiz arıza tipi, birden fazla sensörde eş zamanlı ve fiziksel olarak tutarlı imzalar üretecek "
"biçimde modellenmiştir. Her senaryoda sistem, anomaliyi tespit eder, kalan ömrü tahmin eder ve teknik "
"asistan üzerinden ilgili çözüm dokümanına yönlendirir.")
pdf.tablo(["Arıza senaryosu", "Sensör imzası", "Baskın gösterge"],
    [["Yağ / hidrolik pompa arızası", "Basınç düşer, titreşim artar, yağ sıcaklığı düşer, yakıt artar", "Basınç (düşük)"],
     ["Rulman aşınması", "Titreşim belirgin yükselir, sıcaklık hafif artar", "Titreşim"],
     ["Motor aşırı ısınması", "Yağ sıcaklığı kritik eşiğe çıkar, akım artar", "Sıcaklık"],
     ["Enjektör / yanma arızası", "Düzensiz yanma titreşimi, yakıt artar, tork düşer", "Titreşim"],
     ["Aşırı akım (motor sargı)", "Akım sürekli üst sınırın üzerinde, sargı ısınır", "Akım"],
     ["Fren aşırı ısınması", "Sıcaklık yükselir, hız düşer, titreşim artar", "Sıcaklık (fren)"],
     ["Transmisyon arızası", "Şanzıman titreşimi ve yağ sıcaklığı artar", "Titreşim"],
     ["Soğutma sistemi arızası", "Motor sıcaklığı sürekli yükselir, akım normaldir", "Sıcaklık"]],
    [50, 84, 46])
pdf.p("Tablo 6. Doğrulanan arıza senaryoları ve çok sensörlü imzaları.", 7.4)

# ─────────────────────────── 9 ───────────────────────────
pdf.h1("9", "Kullanıcı Arayüzü")
pdf.p("Arayüz, tarayıcı üzerinde çalışan hafif ve gerçek zamanlı bir izleme panosudur; ek kurulum "
"gerektirmez. Operatör ve bakım ekibi için üç düzeyde bilgi sunar: filo düzeyinde durum, araç düzeyinde "
"canlı telemetri ve bileşen düzeyinde arıza göstergesi.")
pdf.gorsel(os.path.join(ARAYUZ, "ana-pano.png"),
           "Şekil 4. Canlı izleme panosu — gerçek zamanlı sensör kartları ve zaman serisi grafikleri. "
           "Anomali anları ilgili sensörün grafiğinde işaretlenir.")
pdf.gorsel(os.path.join(ARAYUZ, "dijital-ikiz-2b.png"),
           "Şekil 5. 2B dijital ikiz — yakınlaştırıldıkça ayrıntı düzeyi artar; arızalı bileşen makine "
           "şeması üzerinde işaretlenir.")
pdf.gorsel(os.path.join(ARAYUZ, "anomali-rul.png"),
           "Şekil 6. Anomali tespiti ve LSTM ile üretilen kalan faydalı ömür (RUL) tahmini: arıza, "
           "etkilenen sistem, tahmini kalan ömür ve önerilen aksiyon.")
pdf.gorsel(os.path.join(ARAYUZ, "rag-asistan.png"),
           "Şekil 7. RAG tabanlı Servis Asistanı — doğal dil sorusu ve servis dokümanından üretilen "
           "yanıt, parça numarasıyla birlikte.")
pdf.gorsel(os.path.join(ARAYUZ, "uyarilar.png"),
           "Şekil 8. Uyarılar bölümü — tespit edilen anomaliler, skorları ve otomatik üretilen tahmin.")
pdf.gorsel(os.path.join(ARAYUZ, "filo-secim.png"),
           "Şekil 9. Saha ve araç seçim ekranı — çok sahalı, çok araçlı ve marka-bağımsız filo izleme.")
pdf.gorsel(os.path.join(ARAYUZ, "mail-bildirim.png"),
           "Şekil 10. Kritik anomali anında otomasyon zinciriyle gönderilen gerçek e-posta bildirimi.")

# ─────────────────────────── 10 ───────────────────────────
pdf.h1("10", "Rakip Karşılaştırma")
pdf.p("Uluslararası dev çözümler (Sandvik OptiMine, Cat MineStar Health, Komatsu, Epiroc) güçlüdür; ancak "
"büyük ölçüde yalnızca kendi marka ekipmanlarında çalışır ve hiçbirinde operatöre servis manuelinden anlık "
"çözüm sunan bir anlamsal teknik asistan bulunmamaktadır. Genel amaçlı bakım yönetim (CMMS) yazılımları ise "
"madene ve arıza tahminine özel değildir.")
pdf.tablo(["Özellik", "ÇankaYazılım", "Sandvik OptiMine", "Cat MineStar", "Komatsu", "Epiroc", "Genel CMMS"],
    [["Gerçek zamanlı izleme", "Tam", "Tam", "Tam", "Tam", "Tam", "Tam"],
     ["Anomali tespiti", "Tam", "Tam", "Tam", "Kısmi", "Kısmi", "Kısmi"],
     ["Kalan ömür / arıza tahmini", "Tam", "Kısmi", "Tam", "Kısmi", "Kısmi", "Kısmi"],
     ["RAG teknik asistan (manuelden çözüm)", "Tam", "Yok", "Yok", "Yok", "Yok", "Yok"],
     ["Marka-bağımsız (çok markalı filo)", "Tam", "Yok", "Yok", "Yok", "Yok", "Kısmi"],
     ["Tam kurum içi kurulum / veri egemenliği", "Tam", "Yok", "Yok", "Yok", "Yok", "Kısmi"],
     ["Açık kaynak / sıfır lisans maliyeti", "Tam", "Yok", "Yok", "Yok", "Yok", "Kısmi"],
     ["Ekipman kaynaklı İSG erken uyarı", "Tam", "Kısmi", "Kısmi", "Kısmi", "Kısmi", "Yok"]],
    [56, 24, 22, 20, 18, 18, 22])
pdf.p("Tablo 7. Çözümümüzün mevcut ticari çözümlerle özellik bazında karşılaştırması.", 7.4)
pdf.h2("10.1  Bizi ayıran dört unsur")
pdf.madde([
"Marka-bağımsızlık: Farklı üreticilerin karışık markalı filolarına, mimaride değişiklik gerektirmeden "
"yalnızca konfigürasyon ve bilgi tabanı güncellemesiyle uyarlanabilir.",
"Hibrit yapay zeka: Anomali tespiti ve kalan ömür tahmini tek bir karar destek akışında birlikte çalışır; "
"literatür de hibrit yaklaşımların üstünlüğünü göstermektedir (Bharatheedasan vd., 2025).",
"RAG tabanlı teknik asistan: Üretici bakım manuellerini anlamsal bir arama motoruna dönüştürerek operatöre "
"arıza anında ilgili çözüm bölümünü sunar — bu bileşen sektörde öncüdür.",
"Sıfır lisans maliyeti ve veri egemenliği: Sistem tamamen açık kaynak bileşenlerle kurulur ve kurum içi "
"çalışır; yabancı bulut veya lisans bağımlılığı yoktur, veri işletmenin dışına çıkmaz.",
])

# ─────────────────────────── 11 ───────────────────────────
pdf.h1("11", "Maliyet ve Fayda")
pdf.h2("11.1  Sahip olma maliyeti")
pdf.p("Sistemin ayırt edici ticari özelliği, yazılım tarafında lisans maliyeti taşımamasıdır. Kullanılan "
"tüm bileşenler açık kaynak veya kaynağı açık lisanslıdır ve kurum içi kullanımda ücret gerektirmez. "
"İşletmenin karşılayacağı kalemler yalnızca donanım, kurulum ve bakım tarafındadır.")
pdf.tablo(["Maliyet kalemi", "Durum", "Açıklama"],
    [["Yazılım lisansı", "Yok", "Tüm yığın açık kaynak / fair-code; abonelik veya kullanıcı başı ücret yok"],
     ["Bulut aboneliği", "Opsiyonel", "Sistem kurum içi tek sunucuda çalışabilir; bulut zorunlu değildir"],
     ["Sunucu donanımı", "Orta", "Tek bir endüstriyel sunucu veya edge cihaz yeterlidir"],
     ["Sensör / retrofit", "Değişken", "Verinin çoğu makinenin mevcut sistemlerinde vardır; eksik ölçümler için ek sensör"],
     ["Entegrasyon ve kurulum", "Tek seferlik", "Modbus/OPC-UA/MQTT üzerinden mevcut altyapıya bağlanır"],
     ["Bakım ve güncelleme", "Düşük", "Mikroservis yapısı sayesinde bileşenler bağımsız güncellenir"]],
    [42, 28, 110])
pdf.p("Tablo 8. Sahip olma maliyeti kalemleri.", 7.4)

pdf.h2("11.2  Beklenen fayda")
pdf.p("Kestirimci bakımın etkisi literatürde ölçülmüştür: plansız duruşlarda %30–50, bakım maliyetlerinde "
"%18–25 azalma (McKinsey, 2020). Ülkemizde raylı sistemler için geliştirilen bir dijital ikiz çalışmasında "
"da bakım maliyetlerinde yaklaşık %12–25 tasarruf öngörülmüştür (Kuş vd., 2023). Bakım giderlerinin toplam "
"üretim maliyetinin %60'ına kadar çıkabildiği bir sektörde, bu oranlar doğrudan kâr etkisi anlamına gelir.")
pdf.kpi([("%30–50", "Plansız duruşlarda\nazalma potansiyeli"),
         ("%18–25", "Bakım maliyetlerinde\nazalma potansiyeli"),
         ("MTTR ↓", "Teknik asistanla\nonarım süresi kısalır"),
         ("İSG ↑", "Arıza kazaya\ndönüşmeden yakalanır")])
pdf.p("Ekonomik faydanın ötesinde iki katkı daha vardır. İş sağlığı ve güvenliği tarafında, fren, hidrolik "
"veya motor kaynaklı ani arızalar fiziksel bir kazaya dönüşmeden yakalanır ve dar, tehlikeli ortamda "
"yapılan acil müdahalelerin yerini kontrollü koşullarda planlı bakım alır. Çevresel tarafta ise motor akımı "
"analiziyle enerji verimliliği desteklenir; gereksiz parça değişiminin önüne geçilerek atık oluşumu ve "
"karbon ayak izi azalır.")
pdf.gorsel(os.path.join(SEMA, "surdurulebilirlik.png"),
           "Şekil 11. Sürdürülebilirlik boyutları: finansal, çevresel ve sosyal/İSG katkıları.",
           genislik=150)

# ─────────────────────────── 12 ───────────────────────────
pdf.h1("12", "Uygulanabilirlik ve Yol Haritası")
pdf.p("Kullanılan yöntemler (Isolation Forest, LSTM, vektör tabanlı RAG) endüstride ve akademide "
"olgunlaşmış, doğrulanmış algoritmalardır; bu durum çözümün teknik riskini düşürür. Sistem, farklı marka ve "
"model ekipmanlarda mimari değişikliğe gidilmeksizin çalışacak şekilde tasarlanmıştır. Mevcut PLC/SCADA "
"altyapılarından gelen telemetri, Modbus ve MQTT endüstriyel protokolleri üzerinden entegre edilebilir.")
pdf.gorsel(os.path.join(SEMA, "yol_haritasi.png"),
           "Şekil 12. Olgunluk ve ticarileşme yol haritası: çalışan prototip, saha pilotu, ürünleşme ve "
           "yaygınlaşma aşamaları.", genislik=160)
pdf.h2("12.1  Sonraki adımlar")
pdf.tablo(["Aşama", "Kapsam", "Çıktı"],
    [["Saha pilotu", "Tek bir işletmede 2–3 makineye gerçek sensör entegrasyonu; modellerin saha verisiyle yeniden eğitilmesi",
      "Gerçek veriyle doğrulanmış model başarımı"],
     ["Servis manuellerinin işlenmesi", "Üretici bakım manuellerinin tam kapsamlı olarak vektör veritabanına aktarılması",
      "Binlerce sayfayı kapsayan teknik asistan"],
     ["Gelişmiş gömme modeli", "Erişim başarımı daha yüksek güncel açık kaynak gömme modellerine geçiş",
      "Daha isabetli doküman erişimi, yine sıfır lisans maliyeti"],
     ["3B dijital ikiz", "Arızanın bileşen düzeyinde üç boyutlu görselleştirilmesi",
      "Operatör için daha anlaşılır arıza gösterimi"],
     ["Ürünleşme", "Çok kiracılı (multi-tenant) yapı, rol tabanlı yetkilendirme, ölçekli izleme",
      "İşletmeler arası yaygınlaştırılabilir ürün"]],
    [46, 84, 50])
pdf.p("Tablo 9. Ticarileşme yol haritası ve sonraki adımlar.", 7.4)
pdf.h2("12.2  Riskler ve azaltma")
pdf.tablo(["Risk", "Azaltma yaklaşımı"],
    [["Gerçek saha verisine erişim güçlüğü", "Fiziksel simülatör ile geliştirme; pilot işletme iş birlikleri; sahadan toplanan veriyle kademeli yeniden eğitim"],
     ["Yeni yazılıma adaptasyon direnci", "Mevcut SCADA/PLC altyapısına dokunmadan, standart protokoller üzerinden paralel kurulum"],
     ["Kritik altyapı siber güvenliği", "Tam kurum içi kurulum; dış servis bağımlılığı yok; verinin işletme dışına çıkmaması"],
     ["Model yanlış alarm riski", "Ardışık teyit kuralı ve ekipman başına kalibrasyon; ölçülen yanlış alarm oranı %0,00"]],
    [56, 124])
pdf.p("Tablo 10. Başlıca riskler ve azaltma yaklaşımları.", 7.4)

# ─────────────────────────── 13 ───────────────────────────
pdf.h1("13", "Proje Ekibi ve İletişim")
pdf.p("Proje, ÇankaYazılım adı altında yürütülmektedir. Sistemin mimarisi, yapay zeka katmanı, backend "
"servisleri, veri altyapısı ve kullanıcı arayüzü uçtan uca geliştirilmiş ve çalışır durumda "
"doğrulanmıştır. Proje, TEKNOFEST 2026 Maden Teknolojileri Yarışması'nda yarı finale kalmıştır.")
pdf.kutu("İletişim",
"Muhammed Hamza KARAMANLI — Takım Kaptanı ve Proje Yöneticisi\n"
"E-posta: hamzakaramanli33@gmail.com  ·  hamzakaramanli2011@outlook.com\n"
f"Kaynak kodu ve teknik dokümantasyon: {GITHUB}", PRIMARY)
pdf.p("Pilot uygulama, teknoloji iş birliği veya ayrıntılı teknik değerlendirme talepleriniz için "
"yukarıdaki adreslerden iletişime geçebilirsiniz. Sistemin canlı demosu talep üzerine sunulabilir.")

# ─────────────────────────── 14 ───────────────────────────
pdf.h1("14", "Kaynakça")
pdf.p("Raporda atıf yapılan başlıca kaynaklar Tablo 1'de künyeleriyle birlikte listelenmiştir. Ek olarak "
"aşağıdaki kurumsal kaynaklar kullanılmıştır:", 9)
pdf.madde([
"McKinsey & Company (2020). Analytics-driven maintenance technologies. — Kestirimci bakımın plansız "
"duruş ve maliyet üzerindeki etkisine ilişkin oranlar.",
"CDC / NIOSH (2024). Machinery- and haulage-related mining fatalities. — Maden kazalarında ekipman "
"kaynaklı ölüm oranları.",
"MSHA — Mine Safety and Health Administration (2021). Nihai kaza raporu, 22 Şubat 2021. — Fren arızası "
"kaynaklı ölümlü iş kazası vakası.",
"Sandvik teknik ürün dokümantasyonu — Simülatörde kullanılan gerçek ekipman çalışma aralıkları.",
])

pdf.output(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "CankaYazilim_Teknik_Ticari_Rapor_TR.pdf"))
print("✅ TR raporu üretildi:", pdf.page_no(), "sayfa")
