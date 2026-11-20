# Data sources / Veri kaynakları

## 1. `predictive_maintenance.csv` — external reference dataset

**Dataset:** *Machine Predictive Maintenance Classification*
**Author:** shivamb (Kaggle)
**Original source:** UCI Machine Learning Repository — *AI4I 2020 Predictive Maintenance Dataset*,
Matzka, S. (2020)
**Licence:** Creative Commons Attribution 4.0 International (CC BY 4.0)
**Link:** <https://www.kaggle.com/datasets/shivamb/machine-predictive-maintenance-classification>

### How it is used in this project

**As of v2, this dataset is not used by any model.** In v1 its failure rate (mean of `Target`,
≈ 3.4%) was passed to the Isolation Forest `contamination` parameter. That was removed: the
dataset describes a different machine type (milling process), and v2 calibrates anomaly scores
directly from healthy-fleet residual quantiles instead. The file is kept for reference only.

### Bu projede nasıl kullanılıyor

**v2 itibarıyla bu veri seti hiçbir modelde kullanılmamaktadır.** v1'de arıza oranı (`Target`
ortalaması, ≈ %3,4) Isolation Forest'ın `contamination` parametresine veriliyordu. Bu kaldırıldı:
veri seti farklı bir makine türünü (talaşlı imalat) tanımlıyor; v2 anomali skorlarını doğrudan
sağlıklı filo artıklarının kantillerinden kalibre ediyor. Dosya yalnız referans olarak tutulur.

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
