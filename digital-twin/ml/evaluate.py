"""
Model Doğrulama — Karne Raporu  (Adım 5'te baştan yazıldı)
------------------------------------------------------------
Çalıştırma: .venv/bin/python ml/evaluate.py

Neden baştan yazıldı?
  Eski hali, modeli Kaggle verisiyle "doğruluyordu" ama kolon eşlemesi
  fiziksel olarak anlamsızdı (titreşim yerine takım aşınması DAKİKASI,
  hız yerine motor DEVRİ konuyordu). Simülatör dünyasında eğitilen bir
  modeli bambaşka bir dağılımda sınamak, sürücü ehliyeti sınavını
  uçak simülatöründe yapmak gibidir — çıkan puanın anlamı yoktur.

Yeni yaklaşım: modeller hangi dünyada çalışacaksa O dünyanın TAZE
(eğitimde görülmemiş, yeni üretilmiş) verisiyle sınanır:

  1) Anomali (Isolation Forest, makine başına):
     • tek-okuma yakalama (recall) ve yanlış alarm oranı (eşik 0.6)
     • OLAY bazında yakalama: gerçekte arıza 4-6 okuma sürer (simülatör
       Adım 4 değişikliği); 5 okumalık arıza olayının EN AZ BİRİNDE
       alarm çalması = olay yakalandı. Demo günü asıl önemli sayı budur.
  2) RUL (LSTM): taze run-to-failure koşularında saat cinsinden ortalama
     mutlak hata (MAE) — "modelin ömür tahmini kaç saat şaşıyor?"
  3) Next-step LSTM: bir sonraki okumayı tahminde, "sonraki değer =
     şimdiki değer" diyen naif tahminciye karşı yüzde iyileşme.

Buradan çıkan sayılar sunumun "test sonuçları" bölümünde kullanılabilir.
"""

import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from data.simulator import (EQUIPMENT_PROFILES, _anomaly_reading,
                            _cycle_for, _stateless_reading_for_phase,
                            generate_degradation_run)
from ml.train import FEATURES, IF_BUNDLE_TMPL, apply_calibration, SEQ_LEN

ESIK = 0.6            # dashboard/alarm eşiği (sunum Slayt 9)
OLAY_UZUNLUGU = 5     # bir arıza olayının sürdüğü okuma sayısı (4-6'nın ortası)


# ─────────────────────────────────────────────────────────────
# 1) ANOMALİ — Isolation Forest karnesi
# ─────────────────────────────────────────────────────────────
def eval_anomaly(n_normal=1000, n_event=150):
    print("═" * 62)
    print("  1) ANOMALİ TESPİTİ (Isolation Forest, makine başına)")
    print("═" * 62)

    for eq_id, profile in EQUIPMENT_PROFILES.items():
        with open(IF_BUNDLE_TMPL.format(eq=eq_id), "rb") as f:
            b = pickle.load(f)
        phases = [p for p, _ in _cycle_for(profile["type"])]

        # DİKKAT (öğrenilen ders): bir okuma dict'i ÖNCE üretilir, sonra
        # 5 sensörü AYNI okumadan çekilir. İlk yazımda her sensör ayrı bir
        # okumadan çekiliyordu → fazları karışmış "Frankenstein" satırlar
        # oluşuyor, model bunlara haklı olarak anomali diyordu.
        def satir(reading: dict) -> list:
            return [reading[k] for k in FEATURES]

        # Taze NORMAL okumalar → yanlış alarm ölçümü
        normal = np.array([
            satir(_stateless_reading_for_phase(
                eq_id, phase=np.random.choice(phases),
                wear=float(np.random.uniform(0.05, 0.5))))
            for _ in range(n_normal)])
        s_n = apply_calibration(b["model"], b["scaler"], b["calib"], normal)

        # Taze ARIZA OLAYLARI → hem tek-okuma hem olay bazında yakalama.
        # Olay = AYNI arıza tipinin OLAY_UZUNLUGU okuma boyunca sürmesi
        # (simülatörün kalıcı enjeksiyon davranışının birebir taklidi).
        FAULTS = {"overheat": ("temperature", 1.3, 1.55),
                  "vibration_spike": ("vibration", 2.0, 3.0),
                  "overcurrent": ("current", 1.4, 1.7),
                  "pressure_surge": ("pressure", 1.4, 1.8)}
        tek_okuma_hits, olay_hits = [], 0
        for _ in range(n_event):
            sensor, lo, hi = FAULTS[np.random.choice(list(FAULTS))]
            rows = []
            for _ in range(OLAY_UZUNLUGU):
                r = _stateless_reading_for_phase(
                    eq_id, phase=np.random.choice(phases),
                    wear=float(np.random.uniform(0.1, 0.4)))
                r[sensor] *= np.random.uniform(lo, hi)   # aynı arıza sürüyor
                rows.append(satir(r))
            s = apply_calibration(b["model"], b["scaler"], b["calib"], np.array(rows))
            tek_okuma_hits.extend(s >= ESIK)
            if (s >= ESIK).any():          # olayın herhangi bir anında alarm çaldıysa
                olay_hits += 1

        print(f"  {eq_id:12s}  yanlış alarm: %{(s_n>=ESIK).mean()*100:5.2f}   "
              f"tek-okuma recall: %{np.mean(tek_okuma_hits)*100:5.1f}   "
              f"OLAY yakalama: %{olay_hits/n_event*100:5.1f}")
    print(f"  (eşik={ESIK}, olay uzunluğu={OLAY_UZUNLUGU} okuma, "
          f"normal örnek={n_normal}, olay sayısı={n_event})")


# ─────────────────────────────────────────────────────────────
# 2) RUL — LSTM kalan ömür karnesi
# ─────────────────────────────────────────────────────────────
def eval_rul(n_runs=12):
    print("\n" + "═" * 62)
    print("  2) KALAN FAYDALI ÖMÜR (LSTM RUL)")
    print("═" * 62)
    from app.services.lstm_predictor import predict_rul   # canlıdaki aynı yol

    errors = []
    for eq_id in EQUIPMENT_PROFILES:
        for _ in range(n_runs):
            run = generate_degradation_run(eq_id)          # taze ölüm filmi
            # Filmin farklı sahnelerinden pencereler al (başı/ortası/sonu)
            for frac in (0.3, 0.6, 0.9):
                end = int(len(run) * frac)
                if end < SEQ_LEN:
                    continue
                win = run.iloc[end - SEQ_LEN:end]
                seq = win[FEATURES].values.tolist()
                gercek = float(win["rul_hours"].iloc[-1])
                tahmin = predict_rul(seq, eq_id).get("rul_saat", 0.0)
                errors.append(abs(tahmin - gercek))
    errors = np.array(errors)
    print(f"  Ortalama mutlak hata (MAE): {errors.mean():.1f} saat   "
          f"medyan: {np.median(errors):.1f} saat   (n={len(errors)} pencere)")
    print("  Yorum: eşikler 24 sa / 8 sa olduğundan, birkaç saatlik sapma "
          "karar sınıfını nadiren değiştirir.")


# ─────────────────────────────────────────────────────────────
# 3) NEXT-STEP LSTM — naif tahminciye karşı
# ─────────────────────────────────────────────────────────────
def eval_next_step():
    print("\n" + "═" * 62)
    print("  3) SONRAKİ DEĞER TAHMİNİ (next-step LSTM  vs  naif)")
    print("═" * 62)
    from data.simulator import generate_historical
    from app.services.lstm_predictor import predict

    df = generate_historical(hours=3, interval_seconds=30)   # taze sıralı akış
    lstm_err, naive_err = [], []
    for eq_id, grp in df.sort_values("time").groupby("equipment_id"):
        vals = grp[FEATURES].values
        for i in range(SEQ_LEN, len(vals) - 1, 7):           # 7'şer atlayarak örnekle
            window = vals[i - SEQ_LEN:i].tolist()
            gercek = vals[i]
            tahmin = predict(window)
            if "error" in tahmin:
                continue
            t = np.array([tahmin[k] for k in FEATURES])
            lstm_err.append(np.abs(t - gercek))
            naive_err.append(np.abs(vals[i - 1] - gercek))    # naif: "aynı kalır"
    lstm_mae, naive_mae = np.mean(lstm_err, axis=0), np.mean(naive_err, axis=0)
    print(f"  {'sensör':12s} {'LSTM MAE':>10s} {'naif MAE':>10s} {'iyileşme':>9s}")
    for i, k in enumerate(FEATURES):
        iyi = (1 - lstm_mae[i] / naive_mae[i]) * 100
        print(f"  {k:12s} {lstm_mae[i]:10.2f} {naive_mae[i]:10.2f} {iyi:+8.0f}%")


if __name__ == "__main__":
    np.random.seed(7)   # rapor tekrarlanabilir olsun
    eval_anomaly()
    eval_rul()
    eval_next_step()
    print("\nKarne tamamlandı — bu sayılar sunumun 'test sonuçları' bölümünde kullanılabilir.")
