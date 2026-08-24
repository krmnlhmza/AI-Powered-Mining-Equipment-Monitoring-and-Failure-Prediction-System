# Data sources / Veri kaynakları

## 1. `predictive_maintenance.csv` — external reference dataset

**Dataset:** *Machine Predictive Maintenance Classification*
**Author:** shivamb (Kaggle)
**Original source:** UCI Machine Learning Repository — *AI4I 2020 Predictive Maintenance Dataset*,
Matzka, S. (2020)
**Licence:** Creative Commons Attribution 4.0 International (CC BY 4.0)
**Link:** <https://www.kaggle.com/datasets/shivamb/machine-predictive-maintenance-classification>

### How it is used in this project

This dataset is **not used to train any model.** The only value taken from it is the
**realistic failure rate** — the mean of the `Target` column (≈ 3.4%).

That rate is passed to the `contamination` parameter of the Isolation Forest so the anomaly
detector is calibrated against a realistic proportion of faults rather than an arbitrary guess.

**Used in:** [`ml/train.py`](../ml/train.py) → `_kaggle_failure_rate()`

If the file is missing, the code falls back to an industry-average assumption of 5% and continues
to work normally.

### Bu projede nasıl kullanılıyor

Bu veri seti **hiçbir modeli eğitmek için kullanılmaz.** Ondan alınan tek bilgi, **gerçekçi arıza
oranıdır** — `Target` sütununun ortalaması (≈ %3,4).

Bu oran, Isolation Forest'ın `contamination` parametresine verilir; böylece anomali tespiti
rastgele bir varsayım yerine gerçekçi bir arıza oranına göre kalibre edilir.

**Kullanıldığı yer:** [`ml/train.py`](../ml/train.py) → `_kaggle_failure_rate()`

Dosya bulunmazsa kod, endüstri ortalaması olan %5 varsayımına düşer ve normal çalışmaya devam eder.

---

## 2. `simulator.py` — physics-based digital twin simulator

All sensor data used to **train and validate** the models is produced by the digital twin simulator
in [`simulator.py`](simulator.py).

The simulator does not generate random numbers. It is anchored to the **real operating ranges
published in manufacturer technical documentation** (Sandvik LH517i / TH551i specification sheets)
and preserves the physical relationships between sensors: as load rises, temperature, current and
vibration rise together; engine speed drives vibration and fuel consumption; downhill running
engages the engine brake, dropping torque and cooling the machine; hydraulic actions spike the
pressure. Wear accumulates with operating hours and controlled Gaussian noise mimics real sensor
behaviour.

Modelleri **eğitmek ve doğrulamak** için kullanılan tüm sensör verisi, [`simulator.py`](simulator.py)
içindeki dijital ikiz simülatöründen üretilir. Simülatör rastgele sayı üretmez; üreticinin resmî
teknik dokümanlarındaki gerçek çalışma aralıklarını esas alır ve sensörler arasındaki fiziksel
bağıntıları korur.

> **Note / Not:** Manufacturer specification documents are **not** redistributed in this repository.
> Üretici teknik dokümanları bu depoda **dağıtılmamaktadır.**
