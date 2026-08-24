# Proje Rehberi

Maden iş makinelerinde anomali tespiti + arıza tahmini + RAG teknik asistan.

---

## 1. Çalıştırma (5 adım)

```bash
# 0. Docker Desktop'ı aç (sağ üstte balina ikonu yeşil olmalı)

# 1. Klasöre gir
cd "/Users/muhammedhamzakaramanli/Desktop/adsız klasör/digital_twin-main"

# 2. Altyapıyı kaldır (DB, Qdrant, Redis, MQTT, n8n, Grafana)
docker compose up -d

# 3. Python ortamı (yalnızca ilk seferde)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4. Modelleri eğit (yalnızca ilk seferde)
python ml/train.py

# 5. Backend'i başlat
uvicorn main:app --reload
```

Sonra tarayıcıdan aç:
- **Canlı dashboard:** http://localhost:8000/static/demo.html
- **API:** http://localhost:8000/docs
- **Grafana:** http://localhost:3000 (admin / admin123)
- **n8n:** http://localhost:5678 (admin / admin123)
- **Qdrant:** http://localhost:6333/dashboard

---

## 2. Hangi dosya ne yapar?

| Yol | İş |
|---|---|
| `main.py` | FastAPI uygulamasını başlatır, MQTT abonesi + canlı yayın açar |
| `data/simulator.py` | Sensör verisi üretir (sıcaklık, titreşim, basınç, akım, hız, metan) |
| `data/mqtt_publisher.py` | Üretilen veriyi MQTT broker'a yollar (saha gateway taklidi) |
| `app/services/mqtt_subscriber.py` | MQTT'den okur → anomali tespiti → DB/Redis/n8n/Qdrant |
| `app/services/anomaly_detector.py` | Isolation Forest ile anomali tespiti |
| `app/services/lstm_predictor.py` | LSTM ile sensör tahmini + RUL (kalan ömür) |
| `app/services/rag_service.py` | Sandvik LH517 bilgi tabanı, Qdrant arama |
| `app/services/embedding_service.py` | Anomali geçmişini Qdrant'a gömer |
| `app/services/n8n_notifier.py` | Anomalide n8n webhook tetikler |
| `app/routers/` | HTTP endpoint'leri (sensors, anomalies, predict, rag, dashboard) |
| `app/models/sensor.py` | DB tabloları (SensorReading, AnomalyLog) |
| `app/schemas/sensor.py` | API giriş/çıkış şemaları (Pydantic) |
| `ml/train.py` | Isolation Forest + LSTM + RUL eğitimi |
| `ml/evaluate.py` | Model metrik raporu (ROC-AUC, confusion matrix) |
| `static/demo.html` | Canlı web dashboard (Chart.js, 1098 satır) |
| `docker-compose.yml` | Altyapı servisleri |

---

## 3. Bilinen eksikler

- `app/services/anomaly_detector.py` → `_describe()` eşikleri Kaggle birimleriyle (vibration > 200 vs.). Simülatör birimleriyle uyumsuz, düzeltilmeli.
- Makineler jenerik (`conveyor_01`, `pump_01`, `crusher_01`). Sandvik LH517i / TH551i ile değiştirilmeli.
- RAG'de LLM yok — sadece retrieval. Ollama eklenirse tam olur (opsiyonel).

---

## 4. Sorun olursa

| Sorun | Çözüm |
|---|---|
| `docker: command not found` | Docker Desktop kurulu değil/açık değil |
| `port already in use` | Yerel PostgreSQL/Redis kapat: `brew services stop postgresql` |
| Dashboard'da veri akmıyor | `docker compose ps` ile servisleri kontrol et, `python ml/train.py` çalıştırıldı mı? |
| RAG'de "12 bilgi bloğu" görünmedi | `docker compose restart qdrant` sonra uvicorn'u yeniden başlat |
| Modeller bulunamadı | `python ml/train.py` çalıştır |

Durdurma: `Ctrl+C` (uvicorn) + `docker compose down`
