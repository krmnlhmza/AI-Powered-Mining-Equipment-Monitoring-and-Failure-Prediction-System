<div align="center">


# AI-Powered Mining Equipment Monitoring and Failure Prediction System

**A digital-twin based predictive maintenance platform for heavy mining equipment**

Anomaly detection · Remaining useful life prediction · RAG technical assistant · Autonomous action

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-compose-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![License cost](https://img.shields.io/badge/license%20cost-%240-0D5A4C)](#why-it-matters)

📄 **[Technical & Commercial Report (EN)](docs/report/CankaYazilim_Technical_Commercial_Report_EN.pdf)** · **[Teknik ve Ticari Rapor (TR)](docs/report/CankaYazilim_Teknik_Ticari_Rapor_TR.pdf)** · 🇹🇷 **[Türkçe README](README.tr.md)**

</div>

---

## Overview

In underground mining, heavy equipment is the backbone of the operation — yet its health is still managed
reactively: intervention happens only *after* a failure. This carries three costs: maintenance expenditure
that can reach **60% of total production cost**, roughly **2.5 TB of sensor data generated per machine per
day of which only ~1% is used**, and equipment-related accidents that account for **more than 40% of the
most severe injuries** in underground mining.

This system continuously monitors heavy equipment on a **digital twin**, predicts failures *before* they
occur, and delivers the corrective procedure to the operator instantly. Unlike passive monitoring
dashboards — what the literature calls a *digital shadow* — it does not merely display data: it converts
data into a decision and triggers an automated action chain.

> **Status:** working end-to-end prototype. Semi-finalist, TEKNOFEST 2026 Mining Technologies Competition.

## Why it matters

| | |
|---|---|
| **0.00%** | False alarm rate across 2,250 readings under normal operating conditions |
| **100%** | Detection rate across 480 fault events (8 failure types × 3 machines) |
| **$0** | Software licence cost — the entire stack is open source / fair-code |
| **On-premise** | Runs fully inside your own infrastructure; data never leaves the operation |

## Key capabilities

- **Physics-based digital twin** — duty cycle, thermal inertia and time-evolving damage processes for 8
  components; faults are not "injected and gone", they physically develop. Live stream and training
  data come from the same engine.
- **Real-time anomaly detection** — Isolation Forest plus a residual control limit on normal-behaviour-
  model (NBM) residuals, with per-machine commissioning baseline and 3-reading confirmation.
- **Remaining useful life (RUL) prediction** — an LSTM over operating-hour snapshot sequences; RUL in
  hours plus the component expected to fail (8 classes + healthy).
- **RAG technical assistant** — manufacturer service manuals embedded into a Qdrant vector database;
  natural-language questions are answered from source documentation. Below the similarity threshold the
  system says *"no reliable match found"* rather than hallucinating.
- **Autonomous action** — critical anomalies trigger an n8n workflow that sends a notification, generates a
  PDF report and writes a system log entry in parallel.
- **Vendor independent** — adapts to mixed-brand fleets with configuration changes only, no architectural
  rework.
- **Physics-grounded digital twin simulator** — models real operating ranges from manufacturer
  specifications, with correlated sensors, wear accumulation and measurement noise.

## Screenshots

| Live monitoring dashboard | 2D digital twin (component level) |
|---|---|
| ![Dashboard](docs/images/arayuz/ana-pano.png) | ![Digital twin](docs/images/arayuz/dijital-ikiz-2b.png) |
| Real-time sensor cards and time-series charts. Anomalies are marked on the affected sensor's chart. | Level of detail increases as you zoom; the faulty component is highlighted on the schematic. |

| Anomaly + RUL prediction | RAG service assistant |
|---|---|
| ![RUL](docs/images/arayuz/anomali-rul.png) | ![RAG](docs/images/arayuz/rag-asistan.png) |
| The failure, affected system, estimated remaining life and recommended action. | A natural-language question answered from service documentation, with part numbers. |

| Alerts panel | Fleet / site selection |
|---|---|
| ![Alerts](docs/images/arayuz/uyarilar.png) | ![Fleet](docs/images/arayuz/filo-secim.png) |
| Detected anomalies with scores and the automatically generated prediction. | Multi-site, multi-machine, vendor-independent fleet monitoring. |

| Simulator operating conditions | Automated e-mail notification |
|---|---|
| ![Simulator](docs/images/arayuz/simulator-kosullar.png) | ![Mail](docs/images/arayuz/mail-bildirim.png) |
| Physical operating-condition scenarios of the digital twin. | A real notification dispatched by the automation chain. |

## Architecture

<div align="center">
<img src="docs/images/semalar/mimari.png" alt="System architecture" width="640">
</div>

Five microservice layers, all packaged with Docker Compose:

```
Field sensors / simulator
        │  Modbus · OPC-UA · MQTT  →  normalised JSON
        ▼
Eclipse Mosquitto (MQTT broker)
        ▼
Subscriber service ──┬──▶ TimescaleDB   (persistent time series)
                     ├──▶ Redis         (live latest state)
                     └──▶ Anomaly detection → RUL → n8n automation
        ▼
FastAPI backend  ──▶  Qdrant (vector DB, RAG)
        ▼
Browser dashboard · 2D digital twin · RAG assistant
```

| Layer | Component | Role |
|---|---|---|
| Runtime | Python 3.12, FastAPI, Uvicorn | Asynchronous REST services |
| Time series | TimescaleDB (PostgreSQL) | Persistent sensor history |
| Cache | Redis | Live latest state for the UI |
| Vector DB | Qdrant | Semantic search over service docs |
| Messaging | Eclipse Mosquitto (MQTT 3.1.1) | Real-time field data path |
| ML | scikit-learn, PyTorch | Isolation Forest, LSTM |
| Automation | n8n | Notification, PDF report, logging |
| Packaging | Docker, Docker Compose | Single-command deployment |

## Quick start

**Requirements:** Docker Desktop and Python 3.12.

```bash
git clone https://github.com/krmnlhmza/AI-Powered-Mining-Equipment-Monitoring-and-Failure-Prediction-System.git
cd AI-Powered-Mining-Equipment-Monitoring-and-Failure-Prediction-System/digital-twin

cp .env.example .env          # adjust credentials and notification recipients
docker compose up -d          # TimescaleDB, Redis, Qdrant, Mosquitto, n8n

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn main:app --port 8000
```

Then open **<http://localhost:8000>**.

> On first launch the embedding model is downloaded from Hugging Face (one-off, a few GB), so the first
> start takes longer than subsequent ones.

**Training the models** (optional — pre-trained models ship with the repository):

```bash
python ml/train.py            # NBM + Isolation Forest + RUL LSTM + forecaster (~6 min)
python ml/evaluate.py         # honest scorecard on unseen machines
```

## Repository layout

```
digital-twin/            Application
├── app/
│   ├── routers/         REST endpoints (sensors, anomalies, predict, rag, reports)
│   ├── services/        Anomaly detection, LSTM/RUL, RAG, mailer, n8n, PDF report
│   ├── adapters/        Modbus · OPC-UA · MQTT field adapters
│   └── models/          Database models
├── data/                Digital twin simulator and MQTT publisher
├── ml/                  Training scripts and trained models
├── static/              Browser interface
├── n8n_workflows/       Automation workflow definition
└── docker-compose.yml   Infrastructure services

docs/
├── report/              Technical & commercial report (TR / EN)
└── images/              Interface screenshots and diagrams
```

## Validation

`ml/evaluate.py` measures on freshly generated machines never seen in training, using the exact live
decision rule (results: `digital-twin/ml/artifacts/evaluation.json`):

| Test | Scope | Result |
|---|---|---|
| False alarms, healthy fleet | 240 machines, ~144k operating hours | loader 0.36 · truck 0.10 episodes / 1000 h |
| Detected before failure | 480 run-to-failure units, 8 components | 100% · median lead time 64–67 h |
| RUL error (all windows) | 20,466 windows, 400 machines | LSTM RMSE 21.3 h · GBM 24.5 · constant 50.4 |
| RUL error (last 30 h) | 3,067 windows | LSTM RMSE 8.8 h · GBM 13.2 |
| Component diagnosis (RUL < 72 h) | 9 classes | 77.5% (main confusion: cooling ↔ engine overheating) |
| 30 s ahead forecast | 5 sensors vs. persistence baseline | 19–78% lower MAE |

> **Transparency:** these results are on physics-based simulation data — not field data; the
> simulator's assumptions (damage physics, noise, unit-to-unit variation) directly shape them.
> Architecture and error analysis: [`docs/V2_MIMARI.md`](docs/V2_MIMARI.md).

## Validated failure scenarios

Oil/hydraulic pump failure · Bearing wear · Engine overheating · Injector/combustion fault ·
Overcurrent (motor winding) · Brake overheating · Transmission failure · Cooling system failure

Each is modelled to produce simultaneous, physically consistent signatures across multiple sensors.

## Roadmap

- [ ] Field pilot — real sensor integration and retraining on site data
- [ ] Full ingestion of manufacturer service manuals into the vector database
- [ ] Migration to newer open-source embedding models with higher retrieval performance
- [ ] 3D digital twin visualisation
- [ ] Multi-tenant productisation with role-based access control

## Data & attribution

**Training data.** All sensor data used to train and validate the models is generated by the
physics-based digital twin simulator in [`digital-twin/data/simulator.py`](digital-twin/data/simulator.py),
anchored to real operating ranges from manufacturer specification sheets. Manufacturer documents
themselves are not redistributed here.

**External reference dataset.** [`predictive_maintenance.csv`](digital-twin/data/predictive_maintenance.csv)
is the *Machine Predictive Maintenance Classification* dataset by **shivamb** on Kaggle, derived from
the UCI *AI4I 2020 Predictive Maintenance Dataset* (Matzka, S., 2020), licensed **CC BY 4.0**. As of
v2 it is not used by any model (v1 took only the `contamination` rate from it; removed because the
equipment type differs).

Full details: [`digital-twin/data/DATA_SOURCES.md`](digital-twin/data/DATA_SOURCES.md)

## Contact

**Muhammed Hamza KARAMANLI** — Team Lead and Project Manager, ÇankaYazılım

📧 hamzakaramanli33@gmail.com · hamzakaramanli2011@outlook.com

For pilot deployments, technology partnerships or a detailed technical evaluation, please get in touch.
A live demonstration can be provided on request.
