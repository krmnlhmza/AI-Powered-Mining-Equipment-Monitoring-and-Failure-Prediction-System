# v2 Mimari ve Hata Analizi

Bu belge, Teknofest sonrası yenilemeyi (dal: `yenileme-v2`, temel: etiket
`teknofest-v1-snapshot`) ve **neyin neden değiştiğini** açıklar. RAG asistanı
bu yenilemenin kapsamı dışındadır.

## 1. v1'in sorunları (kanıtla)

| Alan | v1'de ne vardı | Neden sorun |
|---|---|---|
| Simülatör | Her okuma = fazın sabit değeri + bağımsız gürültü | Ardışık okumalar arasında fiziksel bağ yok; sıcaklık faz değişince anında zıplıyor |
| Arızalar | 3–4 okumalık basamak enjeksiyonu, ardından kayboluyor; `live_stream.py` her 20 döngüde bir zorla anomali | Gerçek bozulma kademelidir; "döngüyle anomali" öğrenilecek bir süreç değildir |
| Yıpranma | 5000 saatte %100 | Canlı akışta pratikte görünmez |
| Anomali kararı | Enjekte arıza aktifse sonuç **zorla** `True` ("demo garantisi") | Ölçülen başarı modele ait değil |
| RUL | Arıza enjekte edilince **sabit tablo** (`_DEMO_RUL`, ör. rulman = 5,2 sa); aksi halde LSTM çıktısı fizik tavanıyla kırpılıyor | Gösterilen RUL model tahmini değil |
| RUL eğitim/servis | Eğitimde adım = 30 dk; canlıda 20 okuma × ~3–8 sn | Model hiç görmediği zaman ölçeğinde çalıştırılıyor → tahmin yapamaması kaçınılmaz |
| Next-step LSTM | "Naife göre %91 iyileşme" | Veri i.i.d. gürültü; naif tahmin gürültüyü iki kez sayar, LSTM faz ortalamasını söyler — gerçek dinamik öğrenimi değil |
| Değerlendirme | Eğitimle aynı üreteçle, aynı tip sentetik anomali | Döngüsel; genellemeyi ölçmez |
| `contamination` | Kaggle AI4I (talaşlı imalat) arıza oranı | Farklı makine türü |

## 2. v2 mimarisi

```
                       ┌──────────── Dijital İkiz (data/simulator.py) ────────────┐
                       │  operasyon döngüsü → komut (gaz, yük, hız, hidrolik)      │
                       │  1. mertebe dinamik (devir, hız, tork, akım, basınç)      │
                       │  toplu ısıl model  dT/dt = (T_denge − T)/τ,  τ = 4 dk      │
                       │  8 bileşen: Weibull kuluçka + dD/dh = g·s(t)·(D+0.05)     │
                       │  makineler arası fark + sensör kalibrasyon sapması        │
                       └───────────────┬─────────────────────────────┬────────────┘
                     canlı (N=1, 3 sn) │                             │ eğitim (N=yüzlerce, aynı motor)
                                       ▼                             ▼
   okuma ─► bağlam (devir/tork/hız + EWMA 60 s, 240 s) ─► Normal Davranış Modeli (HistGBR)
                                                            │ beklenen değer
                         artık z = (ölçülen − beklenen)/σ ◄─┘
                         − makinenin devreye alma ortalaması (ilk 100 okuma)
                                       │
               ┌───────────────────────┼───────────────────────────┐
               ▼                                                   ▼
   yumuşatılmış z → Isolation Forest  ┐            4 çalışma saatlik özetler
                 → artık limiti max|z|├─ skor      [ort. z, std z, ort. bağlam]
                   (kalibre, max)     ┘                     │ ≤30 özet
               3 ardışık ≥ 0.6 → anomali                    ▼
                                                   RUL LSTM → kalan ömür (sa)
                                                            → bileşen (8 + sağlıklı)
```

**İki saat.** Hasar saati fiziksel saatten `SIM_AGING_ACCEL` (varsayılan 600)
kat hızlı akar: canlı demoda yüzlerce saatlik bir bozulma ~10–15 dakikada
izlenir. Okumalardaki `op_hours` (motor saat sayacı) hasar saatini taşır; RUL
özetleri buna göre pencerelenir, bu yüzden hızlandırma oranı değişse de model
girdisi aynı anlamı taşır.

**Eğitim = servis.** `ml/features.py` canlı (okuma okuma) ve toplu (eğitim)
yolları aynı özyinelemeyle uygular; `ml/evaluate.py` bölüm 0 bunu sayısal
olarak doğrular (fark = 0).

**Gerçek RUL bilinir.** Simülatör hasar denkleminden gerçek RUL'u analitik
hesaplar (`twin_status`, `GET /sensors/twin/{id}`). Modellere girdi olarak
verilmez; yalnız değerlendirme içindir.

## 3. Sonuçlar (yeni makinelerde, `ml/artifacts/evaluation.json`)

| Ölçüm | Yükleyici | Kamyon |
|---|---|---|
| Yanlış alarm olayı / 1000 çalışma saati (sağlıklı filo) | 0,36 | 0,10 |
| Arızadan önce yakalama | %100 | %100 |
| Medyan öncü süre (ilk alarm → arıza) | 67 sa | 64 sa |

| RUL | RMSE (tümü) | RMSE (RUL ≤ 100) | RMSE (RUL ≤ 30) |
|---|---|---|---|
| Sabit ortalama | 50,4 | 54,1 | 80,9 |
| GBM, yalnız son özet (zamansal değil) | 24,5 | 26,6 | 13,2 |
| **LSTM, özet dizisi** | **21,3** | **23,2** | **8,8** |

Bileşen teşhisi: RUL < 72 sa pencerelerde %77,5. 30 sn ileri tahminde LSTM,
"değişmez" referansına göre MAE'yi sensöre göre %19–78 düşürüyor.

## 4. Bilinen sınırlar (paper'da açıkça yazılmalı)

1. **Simülasyon verisi.** Tüm sayılar simülatörün varsayımlarına bağlıdır.
   Hasarın sensörlere yansıma kanalları (ör. rulman → titreşim) tasarım gereği
   temizdir; gerçek veride örtüşme ve ölçüm sorunları daha fazladır.
2. **Soğutma ↔ motor ısınması karışıyor.** Mevcut sensör setinde iki arıza
   neredeyse aynı imzayı (yalnız sıcaklık artışı) verir; ayırt etmek için
   soğutucu giriş/çıkış sıcaklığı veya fan devri gibi ek sensör gerekir. Bu bir
   model hatası değil, gözlemlenebilirlik sınırıdır.
3. **Erken dönem RUL belirsizliği.** Hasar ilk %10'unda sensörlere yansımaz;
   bu bölgede model haklı olarak "uzak" (≈ üst sınır) der. Etiketler 150 saatte
   kırpılır (C-MAPSS'teki parçalı doğrusal yaklaşım).
4. **Devreye alma sırasında başlayan arıza** makinenin "normali" sayılabilir
   (ilk 100 okuma). Sahada devreye alma bakım sonrası yapılmalıdır.
5. **Tek arıza varsayımı (eğitim).** Run-to-failure filosunda her makinede bir
   bileşen bozulur; eşzamanlı çoklu arıza eğitimde temsil edilmiyor.
6. **Kuluçkadaki arızalar öngörülemez.** `project_future` yalnız başlamış
   hasarları ilerletir.

## 5. Yeniden üretme

```bash
cd digital-twin
.venv/bin/python ml/train.py      # ~6 dk (CPU)
.venv/bin/python ml/evaluate.py   # ~2 dk
```

## 6. Sonraki adımlar

- Gerçek/açık veriyle dış doğrulama: NASA C-MAPSS (RUL), NASA/IMS veya CWRU
  rulman veri setleri (titreşim) — simülatör bulgularının taşınabilirliğini sınar.
- RUL için belirsizlik aralığı (ör. MC dropout veya kantil kaybı).
- AssetOpsBench'e maden senaryosu olarak katkı (endüstriyel ajan değerlendirmesi).
