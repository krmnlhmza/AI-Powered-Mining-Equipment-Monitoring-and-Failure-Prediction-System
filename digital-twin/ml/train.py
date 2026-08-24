"""
Model Eğitimi
-------------
Çalıştırma: python ml/train.py

1. Isolation Forest  → gerçek Kaggle verisiyle eğitilir
2. LSTM              → simüle zaman serisiyle eğitilir
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd
import numpy as np
import pickle
import torch
import torch.nn as nn
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

DATA_PATH  = "data/predictive_maintenance.csv"
IF_PATH    = "ml/isolation_forest.pkl"
SCALER_PATH = "ml/scaler.pkl"
LSTM_PATH  = "ml/lstm_model.pt"


# ─────────────────────────────────────────────
# 1. Isolation Forest — EKİPMAN BAŞINA model + skor kalibrasyonu
# ─────────────────────────────────────────────
# Neden yenilendi (Adım 4)?
#   Eski hali: tüm makineler TEK modelde + ham skor "0.5 - score_samples"
#   formülüyle 0-1'e sıkıştırılıyordu. Sonuç: normal okumalar bile ~0.92
#   skor alıyor, 0.6/0.7 eşikleri hiçbir şey ayırt etmiyordu.
#   Yeni hali: her makineye kendi modeli (sunumdaki "her makinenin kendi
#   normal karakteristiği öğrenilir" cümlesinin karşılığı) + skor,
#   normal/arızalı veri dağılımlarına göre KALİBRE ediliyor.

FEATURES = ["temperature", "vibration", "pressure", "current", "speed"]
IF_BUNDLE_TMPL = "ml/if_{eq}.pkl"   # ekipman başına model paketi


def _kaggle_failure_rate() -> float:
    """Gerçekçi arıza oranını harici referans veri setinden okur.

    VERİ KAYNAĞI (atıf):
        "Machine Predictive Maintenance Classification" — Kaggle, shivamb.
        Kaynağı: UCI "AI4I 2020 Predictive Maintenance Dataset"
        (Matzka, S., 2020), CC BY 4.0 lisanslı.
        Dosya: data/predictive_maintenance.csv

    NOT: Bu veri seti modelleri EĞİTMEK için kullanılmaz. Ondan alınan tek
    bilgi, gerçek sahadaki arıza oranıdır (Target sütununun ortalaması,
    ~%3,4). Bu oran Isolation Forest'ın `contamination` parametresine
    verilir. Modellerin eğitim verisi, data/simulator.py içindeki fiziksel
    dijital ikiz simülatöründen üretilir.

    Dosya yoksa endüstri ortalaması %5 varsayılır.
    """
    try:
        return float(pd.read_csv(DATA_PATH)["Target"].mean())   # ~0.034
    except Exception:
        return 0.05


def _calibrate(raw_normal, raw_anom) -> dict:
    """
    Ham IF skorunu (score_samples; DAHA NEGATİF = daha anormal) 0-1'e çeviren
    haritanın çapa noktalarını üretir.

    Mantık: x = -ham_skor dersek büyük x = anormal olur. Dört çapa koyarız:
        normal verinin medyanı  → 0.10  (sağlıklı makine ekranda ~%10 görünsün)
        normalin %99'luk ucu    → 0.50  (normalin en ekstremi bile 0.6'ya değmesin)
        arızalı verinin medyanı → 0.85  (tipik arıza, kritik eşiğin üstünde)
        arızalının %95'i        → 0.98
    Ara değerler doğrusal interpolasyonla (np.interp) bulunur. Böylece
    0.6 = "normalin sınırını aştı", 0.7 = "arıza bölgesine girdi" anlamı kazanır.
    """
    x_norm, x_anom = -np.asarray(raw_normal), -np.asarray(raw_anom)
    # Çapalar KESİN artan sırada olmalı. Normal ve arıza dağılımları
    # örtüşürse (örn. hafif arızalar normalin içine düşerse) arıza çapasını
    # normalin %99 çapasının ÜSTÜNE itiyoruz — böylece "normalin %99'u
    # 0.5'in altında kalır" garantisi (yanlış alarm ≤ ~%1) asla bozulmaz.
    x1 = float(np.median(x_norm))
    # Normalin %99'luk ucu → 0.50. Köşe fazlar (rölanti/soğuma/boşaltma)
    # simülatörde 3x yoğun örneklendiği için bu çapa artık onları 0.6 üstüne
    # itmiyor; kalibrasyonu daha fazla sıkmaya gerek yok (sıkmak arıza recall'ını
    # bozuyordu). Yanlış alarm ölçümü hold-out normalde ~%1 kalır.
    x2 = float(np.quantile(x_norm, 0.99))
    x3 = max(float(np.median(x_anom)),      x2 + 1e-9)
    x4 = max(float(np.quantile(x_anom, 0.95)), x3 + 1e-9)
    return {"xp": [x1, x2, x3, x4], "fp": [0.10, 0.50, 0.85, 0.98]}


def apply_calibration(model, scaler, calib, rows) -> np.ndarray:
    """Ham okumaları kalibre edilmiş 0-1 skora çevirir.
    Eğitimdeki kabul testi ve canlı tespit (anomaly_detector) AYNI yolu kullanır."""
    raw = model.score_samples(scaler.transform(rows))
    return np.clip(np.interp(-raw, calib["xp"], calib["fp"]), 0.0, 1.0)


def train_one_equipment(eq_id: str, df_pool=None, save: bool = True) -> dict:
    """Tek bir ekipman için model eğit + kalibre et. Paket döner:
    {model, scaler, calib}. anomaly_detector eksik model görürse bunu çağırır."""
    from data.simulator import generate_training_data

    if df_pool is None:
        df_pool = generate_training_data(n_samples=9000)
    d = df_pool[df_pool.equipment_id == eq_id]

    # Normal ve arızalı örnekleri AYIR: model yalnız normalden öğrenir,
    # arızalılar sadece kalibrasyon çapası olarak kullanılır.
    normal = d[~d.is_anomaly][FEATURES].values
    anom   = d[d.is_anomaly][FEATURES].values

    # KRİTİK: normal veri ikiye bölünür —
    #   %70'i modelin EĞİTİMİNE girer,
    #   %30'u modelden SAKLANIR ve kalibrasyon çapaları bu saklanan
    #   (hold-out) parçadan hesaplanır.
    # Neden? Model, eğitimde gördüğü noktalara "tanıdık" diye iyimser puan
    # verir; çapaları o iyimser puanlarla kurarsak gerçek (taze) veri
    # eşiği kolayca aşar. İlk denemede bu hatayı yaptık: eğitim verisinde
    # %1 görünen yanlış alarm, taze veride %20-30 çıktı. Hold-out ile
    # çapalar "modelin hiç görmediği normal veri şöyle puan alır"
    # gerçeğine göre kurulur ve taze veri ölçümü eğitim raporuyla tutar.
    rng = np.random.default_rng(42)
    idx = rng.permutation(len(normal))
    kesim = int(len(normal) * 0.7)
    normal_egitim, normal_saklanan = normal[idx[:kesim]], normal[idx[kesim:]]

    # Ölçekleyici de yalnız eğitim parçasından öğrenir
    scaler = StandardScaler().fit(normal_egitim)
    model = IsolationForest(n_estimators=200,
                            contamination=_kaggle_failure_rate(),
                            random_state=42).fit(scaler.transform(normal_egitim))
    calib = _calibrate(model.score_samples(scaler.transform(normal_saklanan)),
                       model.score_samples(scaler.transform(anom)))

    bundle = {"model": model, "scaler": scaler, "calib": calib}
    if save:
        os.makedirs("ml", exist_ok=True)
        with open(IF_BUNDLE_TMPL.format(eq=eq_id), "wb") as f:
            pickle.dump(bundle, f)

    # ── Kabul testi: eşik 0.6 ile tek-okuma performansı ─────────────
    # Yanlış alarm SAKLANAN parçada ölçülür (dürüst, taze-veri tahmini).
    # Not: canlıda arızalar 4-6 ardışık okuma sürer (simulator değişikliği);
    # tek okumada %60-70 yakalama, olay bazında pratikte ~%100 demektir.
    s_n = apply_calibration(model, scaler, calib, normal_saklanan)
    s_a = apply_calibration(model, scaler, calib, anom)
    bundle["kabul"] = {
        "recall_tek_okuma": float((s_a >= 0.6).mean()),
        "yanlis_alarm":     float((s_n >= 0.6).mean()),
        "normal_ort":       float(s_n.mean()),
        "anomali_ort":      float(s_a.mean()),
    }
    return bundle


def train_isolation_forest():
    print("── Isolation Forest (ekipman başına) eğitiliyor ──")
    from data.simulator import EQUIPMENT_PROFILES, generate_training_data
    print(f"  Kaggle arıza oranı (eğitimdeki anomali payı): %{_kaggle_failure_rate()*100:.1f}")

    np.random.seed(42)   # veri üretimi deterministik → retrain'ler kararlı,
    #                      demo modeli seed şansına bağlı kalmaz
    df_pool = generate_training_data(n_samples=12000)  # tüm ekipmanlar tek havuz
    for eq_id in EQUIPMENT_PROFILES:
        b = train_one_equipment(eq_id, df_pool=df_pool)
        k = b["kabul"]
        print(f"  {eq_id:12s} tek-okuma recall=%{k['recall_tek_okuma']*100:5.1f}  "
              f"yanlış_alarm=%{k['yanlis_alarm']*100:4.2f}  "
              f"normal_ort={k['normal_ort']:.2f}  anomali_ort={k['anomali_ort']:.2f}")
    print(f"  Modeller kaydedildi → {IF_BUNDLE_TMPL.format(eq='<ekipman>')}")


# ─────────────────────────────────────────────
# 2. LSTM
# ─────────────────────────────────────────────

SEQ_LEN    = 20
INPUT_SIZE = 5
HIDDEN     = 64
LAYERS     = 2
EPOCHS     = 50


class LSTMModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.lstm = nn.LSTM(INPUT_SIZE, HIDDEN, LAYERS,
                            batch_first=True, dropout=0.2)
        self.fc   = nn.Linear(HIDDEN, INPUT_SIZE)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])


def _make_sequences(data: np.ndarray):
    X, y = [], []
    for i in range(len(data) - SEQ_LEN):
        X.append(data[i : i + SEQ_LEN])
        y.append(data[i + SEQ_LEN])
    return np.array(X), np.array(y)


LSTM_SCALER_PATH = "ml/lstm_scaler.pkl"
BATCH_SIZE = 128


def train_lstm():
    print("\n── LSTM eğitiliyor (zaman-sıralı simülatör verisi) ──")
    # Neden yenilendi (Adım 5)?
    #   Eski hali: generate_training_data'nın KARIŞIK (birbiriyle ilgisiz,
    #   rastgele sıralı) örneklerini zaman serisiymiş gibi dilimliyordu —
    #   pencereler farklı makinelerin okumalarını bile karıştırıyordu.
    #   Böyle eğitilen model trend öğrenemez, ortalamayı söyler.
    #   Yeni hali: generate_historical ile GERÇEK ZAMAN SIRALI 24 saatlik
    #   akış üretilir; pencereler her makinenin KENDİ zaman çizgisinde
    #   dilimlenir (makine sınırı asla aşılmaz). Model artık "bu 20 okumalık
    #   filmden sonraki kare ne olur?" sorusunu gerçekten öğreniyor.

    from data.simulator import generate_historical
    df = generate_historical(hours=24, interval_seconds=30)   # makine başına 2880 sıralı okuma

    features = ["temperature", "vibration", "pressure", "current", "speed"]

    scaler = StandardScaler()
    scaler.fit(df[features].values)
    with open(LSTM_SCALER_PATH, "wb") as f:
        pickle.dump(scaler, f)
    print(f"  LSTM scaler kaydedildi: {LSTM_SCALER_PATH}")

    # Pencereleri makine bazında, zaman sırasına göre dilimle
    X_parts, y_parts = [], []
    for eq_id, grp in df.sort_values("time").groupby("equipment_id"):
        seq_scaled = scaler.transform(grp[features].values)
        X_eq, y_eq = _make_sequences(seq_scaled)
        if len(X_eq):
            X_parts.append(X_eq); y_parts.append(y_eq)
    X_all = np.concatenate(X_parts)
    y_all = np.concatenate(y_parts)
    print(f"  Dizi sayısı: {len(X_all)} (makine sınırı aşılmadan)")

    # CPU kullan (MPS için bellek taşması önlenir)
    device = torch.device("cpu")
    print(f"  Cihaz: {device}")

    X_t = torch.tensor(X_all, dtype=torch.float32)
    y_t = torch.tensor(y_all, dtype=torch.float32)

    dataset   = torch.utils.data.TensorDataset(X_t, y_t)
    loader    = torch.utils.data.DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)

    model     = LSTMModel().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    criterion = nn.MSELoss()

    model.train()
    for epoch in range(1, EPOCHS + 1):
        epoch_loss = 0.0
        for xb, yb in loader:
            optimizer.zero_grad()
            loss = criterion(model(xb), yb)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item()
        if epoch % 10 == 0:
            print(f"  Epoch {epoch:3d}/{EPOCHS} — Loss: {epoch_loss/len(loader):.5f}")

    torch.save(model.state_dict(), LSTM_PATH)
    print(f"  Model kaydedildi: {LSTM_PATH}")


# ─────────────────────────────────────────────
# 3. RUL (Kalan Faydalı Ömür) — LSTM Regresör
# ─────────────────────────────────────────────

RUL_PATH        = "ml/rul_lstm.pt"
RUL_SCALER_PATH = "ml/rul_scaler.pkl"
RUL_MAX_HOURS   = 100.0   # etiket normalizasyonu için tavan
RUL_EPOCHS      = 40


class RULModel(nn.Module):
    """Sensör penceresi → kalan faydalı ömür (normalize 0-1)."""
    def __init__(self):
        super().__init__()
        self.lstm = nn.LSTM(INPUT_SIZE, HIDDEN, LAYERS,
                            batch_first=True, dropout=0.2)
        self.fc   = nn.Linear(HIDDEN, 1)

    def forward(self, x):
        out, _ = self.lstm(x)
        return torch.sigmoid(self.fc(out[:, -1, :]))   # [0,1]


def _rul_sequences(run: np.ndarray, rul: np.ndarray):
    """Tek bir run-to-failure trajektorisinden (pencere → RUL) çiftleri."""
    X, y = [], []
    for i in range(len(run) - SEQ_LEN):
        X.append(run[i : i + SEQ_LEN])
        y.append(rul[i + SEQ_LEN - 1])   # pencere sonundaki RUL
    return X, y


def train_rul():
    print("\n── RUL (Kalan Faydalı Ömür) modeli eğitiliyor ──")
    from data.simulator import generate_rul_dataset

    df = generate_rul_dataset(runs_per_equipment=40)
    features = ["temperature", "vibration", "pressure", "current", "speed"]

    # Tüm run'lar üzerinde tek scaler
    scaler = StandardScaler()
    scaler.fit(df[features].values)
    with open(RUL_SCALER_PATH, "wb") as f:
        pickle.dump(scaler, f)
    print(f"  RUL scaler kaydedildi: {RUL_SCALER_PATH}")

    # Her bağımsız run'ı run_id'ye göre ayrı işle (pencereler run sınırını aşmasın).
    X_all, y_all = [], []
    feat_scaled = scaler.transform(df[features].values)
    rul_vals = df["rul_hours"].values
    n_runs = 0
    for _, idx in df.groupby("run_id").groups.items():
        idx = list(idx)
        run = feat_scaled[idx]
        rul = np.clip(rul_vals[idx] / RUL_MAX_HOURS, 0, 1)
        if len(run) > SEQ_LEN:
            xs, ys = _rul_sequences(run, rul)
            X_all.extend(xs); y_all.extend(ys)
            n_runs += 1

    X_all = np.array(X_all, dtype=np.float32)
    y_all = np.array(y_all, dtype=np.float32).reshape(-1, 1)
    print(f"  Eğitim penceresi: {len(X_all)} (run sayısı: {n_runs})")

    device = torch.device("cpu")
    X_t = torch.tensor(X_all)
    y_t = torch.tensor(y_all)
    loader = torch.utils.data.DataLoader(
        torch.utils.data.TensorDataset(X_t, y_t),
        batch_size=BATCH_SIZE, shuffle=True,
    )

    model     = RULModel().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    criterion = nn.MSELoss()

    model.train()
    for epoch in range(1, RUL_EPOCHS + 1):
        ep = 0.0
        for xb, yb in loader:
            optimizer.zero_grad()
            loss = criterion(model(xb), yb)
            loss.backward()
            optimizer.step()
            ep += loss.item()
        if epoch % 10 == 0:
            # MAE'yi saat cinsine çevir
            mae_h = (ep / len(loader)) ** 0.5 * RUL_MAX_HOURS
            print(f"  Epoch {epoch:3d}/{RUL_EPOCHS} — Loss: {ep/len(loader):.5f}  (~RMSE {mae_h:.1f} saat)")

    torch.save(model.state_dict(), RUL_PATH)
    print(f"  Model kaydedildi: {RUL_PATH}")


# ─────────────────────────────────────────────

if __name__ == "__main__":
    train_isolation_forest()
    train_lstm()
    train_rul()
    print("\nEğitim tamamlandı.")
