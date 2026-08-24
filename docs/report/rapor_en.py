# -*- coding: utf-8 -*-
"""ÇankaYazılım — Technical and Commercial Report (English)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _rapor_ortak import (Rapor, ARAYUZ, SEMA, PRIMARY, ACCENT, RED, MUTED)

GITHUB = "github.com/krmnlhmza/AI-Powered-Mining-Equipment-Monitoring-and-Failure-Prediction-System"

pdf = Rapor("AI-Powered Mining Equipment Monitoring and Failure Prediction System",
            "ÇankaYazılım · Technical and Commercial Report")

pdf.kapak(
    baslik="AI-Powered Mining Equipment\nMonitoring and Failure Prediction System",
    altbaslik="A digital-twin based predictive maintenance platform for heavy mining equipment",
    etiket="Technical and Commercial Report  ·  Working prototype  ·  Fully open-source technology stack\n"
           "Semi-finalist, TEKNOFEST 2026 Mining Technologies Competition",
    yazar_blok="Muhammed Hamza KARAMANLI\nTeam Lead and Project Manager",
    tarih="August 2026",
    iletisim=f"hamzakaramanli33@gmail.com  ·  hamzakaramanli2011@outlook.com\n{GITHUB}")

pdf.add_page()

# ─────────────────────────── 1 ───────────────────────────
pdf.h1("1", "Executive Summary")
pdf.p("In underground mining, heavy equipment is the backbone of the operation. Yet the health of these "
"machines is still managed largely reactively: intervention happens only after a failure occurs. This "
"carries three concrete costs — high maintenance expenditure, sensor data that is lost before it is ever "
"analysed, and fatal accidents caused by equipment failure.")
pdf.p("The system developed by ÇankaYazılım is an integrated predictive maintenance platform that "
"continuously monitors heavy equipment on a digital twin, predicts failures before they occur, and "
"delivers the corrective procedure to the operator instantly. What separates it from the passive "
"monitoring dashboards on the market is that it does not merely display data: it converts data into a "
"decision and triggers an automated action chain (maintenance work order, report, notification).")
pdf.p("The platform rests on a hybrid architecture in which four AI components work together: Isolation "
"Forest for real-time anomaly detection, an LSTM network for remaining useful life (RUL) prediction, a "
"RAG-based technical assistant that retrieves solutions from service documentation, and an n8n automation "
"layer that starts the notification and reporting chain on critical events. The entire technology stack is "
"built from open-source components: there is no software licence cost, and because the system runs fully "
"on-premise, data never leaves the operator's own infrastructure.")
pdf.p("The prototype is operational end to end. In validation testing, 2,250 sensor readings produced "
"under normal operating conditions generated no false alarms, and all 480 fault events created across "
"eight distinct failure types were detected.")
pdf.kpi([("0.00%", "False alarm rate under\nnormal operation"),
         ("100%", "Detection rate across\nfault events"),
         ("$0", "Software licence\ncost"),
         ("8", "Validated failure\nscenarios")])
pdf.kutu("Who is this report for?",
"Mining operators and their maintenance / occupational-safety functions, heavy equipment service "
"providers, industrial digital-transformation and Industry 4.0 investors, and organisations seeking "
"technology partnerships.")

# ─────────────────────────── 2 ───────────────────────────
pdf.h1("2", "Problem Definition")
pdf.p("Underground mining operations must digitalise rapidly to sustain productivity against deepening "
"reserves, declining ore grades and harsh working conditions. The SCADA panels deployed in the field only "
"display sensor data on a screen; because micro-level vibration and current shifts invisible to the human "
"eye are never analysed, approaching failures cannot be seen in advance. The problem manifests along three "
"dimensions.")

pdf.h2("2.1  Maintenance cost")
pdf.p("In heavy industrial operations such as mining, maintenance expenditure can reach up to 60% of total "
"production cost (Savolainen & Urbani, 2021). Under a reactive model the repair itself is often short, but "
"late detection and spare-part waiting times stretch production stoppages into hours or even days, making "
"the operation far more expensive than planned maintenance would.")

pdf.h2("2.2  Wasted data")
pdf.p("An autonomous mining machine generates roughly 2.5 TB of data per day through approximately 180 "
"sensors, yet only about 1% of that data is actually used in decision-making (Don et al., 2025). The "
"remainder is lost unanalysed because systems cannot communicate with one another. What is missing in the "
"field is not sensors or data, but the AI layer that turns that data into a timely, meaningful decision.")

pdf.h2("2.3  Occupational safety")
pdf.p("In underground mining, more than 40% of the most severe accidents result from being struck by or "
"caught in a machine, and 43% of fatalities are associated with heavy haulage equipment such as loaders "
"and trucks (CDC/NIOSH). An equipment failure is therefore not only an economic problem but a life-safety "
"problem, and it must be caught before it becomes a physical accident.")
pdf.kutu("Real case — MSHA Final Report, 22 February 2021",
"In an underground mine, the brakes of a locomotive whose brake shoes had worn below the manufacturer's "
"limit and whose maintenance had been neglected failed to hold, and a 26-year-old operator lost his life. "
"The official report identified the root cause as \"operating with a defective brake system and "
"aggravated conduct\". The case demonstrates that unmonitored equipment wear is not merely costly but "
"lethal — and why predictive maintenance is critical.", RED)

# ─────────────────────────── 3 ───────────────────────────
pdf.h1("3", "Literature and State of the Art")
pdf.p("More than twelve academic studies on anomaly detection, remaining useful life prediction, RAG and "
"digital twins were reviewed during this project. Each of these components is individually mature in the "
"literature; however, no study combines all four in a single, vendor-independent, bidirectional platform. "
"That is precisely the gap this project fills.")
pdf.tablo(
    ["#", "Study (Author, Year & Title)", "Source", "Contribution / finding"],
    [
    ["1", "Savolainen, J. & Urbani, M. (2021). Maintenance optimization for a multi-unit system with digital twin simulation.",
     "Journal of Intelligent Manufacturing, 32(7), 1953–1973.",
     "Mining maintenance up to 60% of production cost; fleet optimisation via digital twin."],
    ["2", "Don, M. G., Wanasinghe, T. R., Gosine, R. G. & Warrian, P. J. (2025). Digital Twins and Enabling Technology Applications in Mining.",
     "IEEE Access, 13, 6945–6963.",
     "Digital twin trends in mining; a machine generates 2.5 TB/day, only 1% is used."],
    ["3", "van Eyk, L. & Heyns, P. S. (2025). A framework to define, design and construct digital twins in the mining industry.",
     "Computers & Industrial Engineering, 200, 110805.",
     "Without bidirectional data flow a system cannot be considered a true 'twin'."],
    ["4", "Kuş, Ş., Tatar, F. & Toprakal, E. (2023). Digital Twin in Rail Systems.",
     "Orclever Proceedings of Research and Development, 3(1), 104–114.",
     "Digital twin (BIM) application in rail systems and resulting cost savings."],
    ["5", "Liu, F. T., Ting, K. M. & Zhou, Z.-H. (2008). Isolation Forest.",
     "2008 Eighth IEEE Int. Conf. on Data Mining (ICDM), 413–422.",
     "Isolation Forest — the foundational anomaly detection algorithm."],
    ["6", "Hochreiter, S. & Schmidhuber, J. (1997). Long Short-Term Memory.",
     "Neural Computation, 9(8), 1735–1780.",
     "LSTM — the base architecture for time series and RUL prediction."],
    ["7", "Neupane, D., Bouadjenek, M. R., Dazeley, R. & Aryal, S. (2025). Data-driven machinery fault diagnosis: A comprehensive review.",
     "Neurocomputing, 627, 129588.",
     "Comprehensive map of data-driven fault diagnosis."],
    ["8", "Muratbakeev, E., Kozhubaev, Y., Novak, D., Ershov, R. & Wei, Z. (2025). Monitoring and Diagnostics of Mining Electromechanical Equipment Based on Machine Learning.",
     "Symmetry, 17(9), 1548.",
     "Machine-learning diagnostics applied directly to mining equipment."],
    ["9", "Bharatheedasan, K., Maity, T., Kumaraswamidhas, L. A. & Durairaj, M. (2025). Enhanced fault diagnosis and RUL prediction of rolling bearings using a hybrid MLP–LSTM network model.",
     "Alexandria Engineering Journal, 115, 355–369.",
     "High performance of hybrid approaches such as ours."],
    ["10", "Lewis, P., Perez, E., Piktus, A., Petroni, F. et al. (2020). Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.",
     "Advances in Neural Information Processing Systems (NeurIPS), 33, 9459–9474.",
     "RAG — the foundational paper behind our technical assistant layer."],
    ["11", "Chen, L.-C., Pardeshi, M. S., Liao, Y.-X. & Pai, K.-C. (2025). Application of retrieval-augmented generation for interactive industrial knowledge management via a large language model.",
     "Computer Standards & Interfaces, 94, 103995.",
     "Semantic access to technical documentation via RAG in industry."],
    ["12", "Cacciuttolo, C., Atencio, E., Komarizadehasl, S. & Lozano-Galant, J. A. (2024). IoT LoRaWAN-Based Wireless Sensors Network for Underground Mine Monitoring.",
     "Sensors, 24(21), 6971.",
     "Underground wireless sensor network (WSN) infrastructure."],
    ],
    [8, 66, 42, 64])
pdf.p("Table 1. Principal studies in the literature and the gap addressed by this project.", 7.4)

# ─────────────────────────── 4 ───────────────────────────
pdf.h1("4", "Solution Approach")
pdf.p("Most systems in the sector are passive monitoring dashboards that merely project sensor data onto a "
"screen; the literature calls these \"digital shadows\" (van Eyk & Heyns, 2025), because they present data "
"in one direction without producing a decision from it. Our solution diverges exactly here: it processes "
"data into a meaningful decision and uses that decision to start an automated action chain without human "
"intervention. This closed decision loop — moving from monitoring to autonomous action — is what makes it "
"a genuine digital twin rather than a passive dashboard.")

pdf.h2("4.1  Mapping problems to solution components")
pdf.tablo(["Problem", "Our solution component", "Outcome"],
    [["Reactive maintenance: high cost and unplanned downtime",
      "Isolation Forest (anomaly) + LSTM (remaining life)",
      "Failures caught days in advance → predictive maintenance"],
     ["99% of sensor data is lost without analysis",
      "Digital twin + AI decision layer",
      "Raw data becomes an instant, autonomous decision"],
     ["Slow access to knowledge → long repair time (MTTR)",
      "RAG-based technical assistant",
      "Procedure retrieved from the manual within seconds"],
     ["Equipment-related occupational safety risk",
      "Anomaly / early-warning layer",
      "Accident prevented before it becomes physical"]],
    [60, 58, 62])
pdf.p("Table 2. Mapping of the identified problems to our solution components and outcomes.", 7.4)

pdf.h2("4.2  Comparison with conventional monitoring")
pdf.tablo(["Aspect", "Conventional monitoring (digital shadow)", "ÇankaYazılım (digital twin)"],
    [["Data flow", "One-way — only displays data on screen", "Data → decision → automated action"],
     ["Decision", "Interpreted by humans, manual intervention", "Automatic anomaly detection + criticality decision"],
     ["Artificial intelligence", "Fixed threshold / single model", "Hybrid: Isolation Forest + LSTM"],
     ["Technical support", "Presents raw data or an error code", "RAG assistant: instant solution from the manual"],
     ["Action", "Passive alarm; the operator must call", "Automatic work order + PDF report + notification"]],
    [34, 73, 73])
pdf.p("Table 3. Conventional monitoring compared with our solution.", 7.4)

# ─────────────────────────── 5 ───────────────────────────
pdf.h1("5", "System Architecture")
pdf.p("The system is built on a five-layer, microservice-based architecture reaching from the field to the "
"user interface. All services are packaged with Docker and Docker Compose, so the platform runs portably "
"on a local (edge) server or in the cloud. Every component can be updated or replaced independently.")
pdf.gorsel(os.path.join(SEMA, "mimari.png"),
           "Figure 1. Five-layer microservice architecture: data acquisition, messaging, data management, "
           "backend & AI, and interface/automation layers.", genislik=132)
pdf.madde([
"Data acquisition (field): Temperature (°C), vibration (mm/s), pressure (bar), current (A), speed (km/h), "
"engine speed (rpm), torque (Nm) and fuel consumption (L/h) are read through the Modbus, MQTT and OPC-UA "
"adapters common in the field, then normalised into a shared JSON schema.",
"Messaging: Each normalised reading is published in real time through an Eclipse Mosquitto MQTT broker. "
"MQTT was chosen because it consumes little bandwidth, has very low latency, and its QoS mechanism "
"preserves message reliability even in underground conditions where connectivity drops.",
"Data management: A subscriber service persists every message to TimescaleDB for time-series queries, "
"writes the latest state to Redis for the live interface, and triggers anomaly detection. Vector "
"representations of technical documents are held in Qdrant.",
"Backend and AI: An asynchronous FastAPI backend exposes the anomaly, RUL and RAG services over REST "
"endpoints.",
"Interface and automation: A browser-based real-time monitoring dashboard, a component-level 2D digital "
"twin view, the technical assistant interface, and an n8n automation that starts the notification chain on "
"critical anomalies.",
])
pdf.h2("5.1  Technology stack")
pdf.tablo(["Layer", "Component", "Role"],
    [["Runtime", "Python 3.12, FastAPI, Uvicorn", "Asynchronous REST services"],
     ["Time series", "TimescaleDB (PostgreSQL extension)", "Persistent sensor history, fast temporal queries"],
     ["Cache", "Redis", "Live latest state; keeps the UI off the disk"],
     ["Vector database", "Qdrant", "Semantic search over service documentation"],
     ["Messaging", "Eclipse Mosquitto (MQTT 3.1.1)", "Real-time field-to-system data path"],
     ["Machine learning", "scikit-learn, PyTorch", "Isolation Forest, LSTM"],
     ["Automation", "n8n", "Notification, PDF report and logging chain"],
     ["Packaging", "Docker, Docker Compose", "Portable, single-command deployment"]],
    [34, 56, 90])
pdf.p("Table 4. Technology stack. All components are open-source or source-available (fair-code) licensed; "
"internal use carries no software licence fee.", 7.4)

# ─────────────────────────── 6 ───────────────────────────
pdf.h1("6", "The Artificial Intelligence Layer")

pdf.h2("6.1  Isolation Forest — real-time anomaly detection")
pdf.p("Each multivariate sensor reading (temperature, vibration, pressure, current and speed) is evaluated "
"by an unsupervised Isolation Forest. The algorithm partitions the data at random to build a large number "
"of decision trees; normal points descend deep into the trees, whereas points that behave differently are "
"isolated in far fewer steps. The model learns each machine's normal operating characteristic in advance "
"and catches deviations from that profile in real time.")
pdf.madde([
"Every machine has its own model; what is 'normal' for a loader is not normal for a haul truck.",
"The raw score is calibrated to a 0–1 range using a held-out validation set. A healthy machine typically "
"stays in the 0.10–0.30 band.",
"Above 0.60 the interface switches to a warning state; critical anomalies above 0.70 trigger the "
"automation chain.",
"A consecutive-confirmation rule provides stability: at least three consecutive readings must exceed the "
"threshold before an anomaly is declared. Isolated noise spikes are filtered out, while genuine failures "
"are confirmed within seconds.",
])

pdf.h2("6.2  LSTM — remaining useful life (RUL) prediction")
pdf.p("To forecast when equipment will fail, a deep-learning LSTM regressor was trained. The model takes a "
"time window of the last 20 sensor readings (5 features × 20 steps) as input and, by learning degradation "
"trends in historical telemetry, produces a normalised health / remaining-life score. This score is scaled "
"into hours and converted into a decision by thresholds: below 24 hours a planned maintenance warning is "
"raised, and below 8 hours an urgent maintenance work order is created.")
pdf.p("The model was trained on hundreds of run-to-failure degradation curves. A threshold-aware hybrid "
"correction is also applied: when a sensor approaches its critical limit, the smaller of a physics-based "
"ceiling and the model estimate is taken. The model therefore stays honest on a healthy machine while "
"remaining life shortens realistically when a failure develops abruptly.")

pdf.h2("6.3  RAG-based technical assistant")
pdf.p("So that the operator can obtain fast and reliable technical support at the moment of failure, "
"manufacturer maintenance manuals are split into meaningful chunks, converted into numerical vectors by an "
"embedding model, and stored in the Qdrant vector database. When the operator asks a question in natural "
"language, that question is embedded with the same model and the semantically closest document sections "
"are retrieved by cosine similarity and presented as the corrective procedure. This reduces dependence on "
"external technical service and shortens mean time to repair (MTTR).")
pdf.kutu("Accuracy principle — no hallucination",
"For questions that fall below the similarity threshold the system does not invent an answer; it returns "
"\"no reliable match found\" and states its coverage explicitly. In industrial maintenance a wrong "
"instruction is more dangerous than no answer. The system only produces responses grounded in source "
"documentation.", PRIMARY)
pdf.p("The embedding model runs entirely locally; queries and documents are never sent to an external "
"service. The current release uses an open-source multilingual embedding model. The roadmap includes "
"migrating to newer open-source models with higher retrieval performance; that migration likewise incurs "
"no additional licence cost.")

pdf.h2("6.4  Autonomous notification and reporting with n8n")
pdf.p("When a critical anomaly is detected, the system posts to the webhook of the n8n automation "
"platform. n8n filters events scoring above 0.70 and, without human intervention, starts three parallel "
"jobs: an instant notification to the maintenance team (e-mail/Slack), generation of a PDF report for the "
"event, and a system log entry. The time between detection and the maintenance team being informed is "
"reduced to seconds.")
pdf.gorsel(os.path.join(SEMA, "n8n_akis.png"),
           "Figure 2. Autonomous notification and reporting workflow: critical anomalies are filtered, "
           "then notification, PDF report and logging jobs are triggered in parallel.", genislik=160)

# ─────────────────────────── 7 ───────────────────────────
pdf.h1("7", "Data Layer and the Digital Twin Simulator")
pdf.p("Real sensor telemetry from underground mining machines is treated as proprietary by manufacturers "
"and is not shared externally. For development and validation we therefore built a digital twin simulator "
"that models the physics of the machine. The simulator does not generate random numbers: it is anchored to "
"the real operating ranges published in the manufacturer's technical documentation and preserves the "
"physical relationships between sensors.")
pdf.madde([
"Equipment profile: Each machine's sensor ranges are taken from the manufacturer's technical "
"documentation (e.g. for an underground loader: temperature 72–88 °C, engine speed 800–2100 rpm, hydraulic "
"pressure 250–280 bar, current 150–195 A).",
"Operating cycle: The machine moves through a realistic duty cycle — idling, approaching the pile, "
"bucket loading, loaded hauling, dumping, returning empty. Conditions such as rough terrain or loaded "
"uphill travel can also be selected manually.",
"Physical correlation: Sensors are not independent. As load rises, temperature, current and vibration "
"rise together; as engine speed increases, vibration and fuel consumption increase; on a downhill run the "
"engine brake engages, torque drops and the machine cools; hydraulic actions spike the pressure.",
"Wear and noise: Wear accumulates with operating hours, and worn bearings shift the vibration and "
"temperature baselines upward. Controlled Gaussian noise mimicking real sensor behaviour is added to every "
"measurement.",
])
pdf.p("The simulator feeds exactly the same path as a real field installation: generated data is published "
"over MQTT and the rest of the system processes it as if it came from a physical sensor. Moving to the "
"field therefore requires no architectural change — the simulator is simply replaced by the real sensor "
"path.")
pdf.gorsel(os.path.join(ARAYUZ, "simulator-kosullar.png"),
           "Figure 3. Physical operating-condition scenarios of the digital twin simulator.", genislik=150)

# ─────────────────────────── 8 ───────────────────────────
pdf.h1("8", "Validation and Test Results")
pdf.p("The system was measured both for its tendency to raise false alarms and for its ability to catch "
"genuine failures. The following results come from automated tests run across three machines and all "
"operating conditions.")
pdf.tablo(["Test", "Scope", "Result"],
    [["False alarms under normal operation",
      "3 machines × all operating conditions, 2,250 sensor readings in total",
      "0 false alarms (0.00%)"],
     ["Fault detection (event-based)",
      "8 fault types × 3 machines × 20 repetitions = 480 fault events",
      "All 480 events detected (100%)"],
     ["End-to-end pipeline",
      "Simulator → MQTT → database → anomaly → RUL → assistant",
      "98,000+ readings processed without interruption"],
     ["Detection latency",
      "3-second publish interval, three-consecutive-reading confirmation",
      "~10 seconds from fault onset to notification"]],
    [46, 74, 60])
pdf.p("Table 5. Validation tests and results.", 7.4)
pdf.kutu("Transparency note",
"These results were obtained on physically grounded simulation data derived from manufacturer "
"specifications; they are not real field data. A production deployment requires the models to be retrained "
"and re-validated on data collected from the site. The architecture is designed so that this retraining "
"can be performed with a single command.", ACCENT)

pdf.h2("8.1  Validated failure scenarios")
pdf.p("Eight fault types were modelled so that they produce simultaneous, physically consistent signatures "
"across multiple sensors. In each scenario the system detects the anomaly, predicts the remaining life and "
"directs the user to the relevant corrective documentation through the technical assistant.")
pdf.tablo(["Failure scenario", "Sensor signature", "Dominant indicator"],
    [["Oil / hydraulic pump failure", "Pressure drops, vibration rises, oil temperature falls, fuel rises", "Pressure (low)"],
     ["Bearing wear", "Vibration rises markedly, temperature rises slightly", "Vibration"],
     ["Engine overheating", "Oil temperature reaches the critical threshold, current rises", "Temperature"],
     ["Injector / combustion fault", "Misfire vibration, fuel rises, torque drops", "Vibration"],
     ["Overcurrent (motor winding)", "Current persistently above the upper limit, winding heats", "Current"],
     ["Brake overheating", "Temperature rises, speed drops, vibration rises", "Temperature (brake)"],
     ["Transmission failure", "Transmission vibration and oil temperature rise", "Vibration"],
     ["Cooling system failure", "Engine temperature rises continuously, current stays normal", "Temperature"]],
    [50, 84, 46])
pdf.p("Table 6. Validated failure scenarios and their multi-sensor signatures.", 7.4)

# ─────────────────────────── 9 ───────────────────────────
pdf.h1("9", "User Interface")
pdf.p("The interface is a lightweight, real-time monitoring dashboard that runs in the browser and "
"requires no additional installation. It presents information to operators and maintenance teams at three "
"levels: fleet-level status, machine-level live telemetry and component-level failure indication.")
pdf.gorsel(os.path.join(ARAYUZ, "ana-pano.png"),
           "Figure 4. Live monitoring dashboard — real-time sensor cards and time-series charts. Anomaly "
           "moments are marked on the chart of the affected sensor.")
pdf.gorsel(os.path.join(ARAYUZ, "dijital-ikiz-2b.png"),
           "Figure 5. 2D digital twin — level of detail increases as the view is zoomed; the faulty "
           "component is highlighted on the machine schematic.")
pdf.gorsel(os.path.join(ARAYUZ, "anomali-rul.png"),
           "Figure 6. Anomaly detection and the LSTM-generated remaining useful life (RUL) estimate: the "
           "failure, the affected system, estimated remaining life and the recommended action.")
pdf.gorsel(os.path.join(ARAYUZ, "rag-asistan.png"),
           "Figure 7. RAG-based service assistant — a natural-language question and the answer produced "
           "from service documentation, including the part number.")
pdf.gorsel(os.path.join(ARAYUZ, "uyarilar.png"),
           "Figure 8. Alerts panel — detected anomalies, their scores and the automatically generated "
           "prediction.")
pdf.gorsel(os.path.join(ARAYUZ, "filo-secim.png"),
           "Figure 9. Site and machine selection screen — multi-site, multi-machine, vendor-independent "
           "fleet monitoring.")
pdf.gorsel(os.path.join(ARAYUZ, "mail-bildirim.png"),
           "Figure 10. A real e-mail notification dispatched by the automation chain on a critical anomaly.")

# ─────────────────────────── 10 ───────────────────────────
pdf.h1("10", "Competitive Comparison")
pdf.p("The major international solutions (Sandvik OptiMine, Cat MineStar Health, Komatsu, Epiroc) are "
"powerful, but they largely operate only on their own branded equipment, and none of them provides a "
"semantic technical assistant that delivers an instant solution from the service manual to the operator. "
"General-purpose maintenance management (CMMS) software, in turn, is not specific to mining or to failure "
"prediction.")
pdf.tablo(["Capability", "ÇankaYazılım", "Sandvik OptiMine", "Cat MineStar", "Komatsu", "Epiroc", "Generic CMMS"],
    [["Real-time monitoring", "Full", "Full", "Full", "Full", "Full", "Full"],
     ["Anomaly detection", "Full", "Full", "Full", "Partial", "Partial", "Partial"],
     ["Remaining life / failure prediction", "Full", "Partial", "Full", "Partial", "Partial", "Partial"],
     ["RAG technical assistant (manual-grounded)", "Full", "None", "None", "None", "None", "None"],
     ["Vendor-independent (mixed fleet)", "Full", "None", "None", "None", "None", "Partial"],
     ["Fully on-premise / data sovereignty", "Full", "None", "None", "None", "None", "Partial"],
     ["Open source / zero licence cost", "Full", "None", "None", "None", "None", "Partial"],
     ["Equipment-driven safety early warning", "Full", "Partial", "Partial", "Partial", "Partial", "None"]],
    [56, 24, 22, 20, 18, 18, 22])
pdf.p("Table 7. Feature-level comparison of our solution against existing commercial offerings.", 7.4)
pdf.h2("10.1  Four differentiators")
pdf.madde([
"Vendor independence: The platform adapts to mixed-brand fleets from different manufacturers with no "
"architectural change — only configuration and knowledge-base updates.",
"Hybrid AI: Anomaly detection and remaining-life prediction operate together in a single decision-support "
"flow; the literature likewise demonstrates the superiority of hybrid approaches (Bharatheedasan et al., "
"2025).",
"RAG-based technical assistant: By turning manufacturer maintenance manuals into a semantic search engine, "
"the system delivers the relevant corrective section to the operator at the moment of failure — a "
"component that is pioneering in this sector.",
"Zero licence cost and data sovereignty: The system is built entirely from open-source components and runs "
"on-premise; there is no foreign cloud or licence dependency, and data never leaves the operation.",
])

# ─────────────────────────── 11 ───────────────────────────
pdf.h1("11", "Cost and Benefit")
pdf.h2("11.1  Total cost of ownership")
pdf.p("The distinguishing commercial property of the system is that it carries no licence cost on the "
"software side. Every component used is open-source or source-available licensed and requires no fee for "
"internal use. The items the operator must fund are limited to hardware, integration and maintenance.")
pdf.tablo(["Cost item", "Status", "Explanation"],
    [["Software licence", "None", "Entire stack open-source / fair-code; no subscription or per-seat fee"],
     ["Cloud subscription", "Optional", "The system can run on a single on-premise server; cloud is not required"],
     ["Server hardware", "Moderate", "A single industrial server or edge device is sufficient"],
     ["Sensors / retrofit", "Variable", "Most data already exists on the machine; extra sensors only for missing measurements"],
     ["Integration and setup", "One-off", "Connects to existing infrastructure over Modbus/OPC-UA/MQTT"],
     ["Maintenance and updates", "Low", "Microservice structure allows components to be updated independently"]],
    [42, 28, 110])
pdf.p("Table 8. Total cost of ownership items.", 7.4)

pdf.h2("11.2  Expected benefit")
pdf.p("The impact of predictive maintenance is measured in the literature: a 30–50% reduction in unplanned "
"downtime and an 18–25% reduction in maintenance cost (McKinsey, 2020). A domestic digital twin study for "
"rail systems likewise projected approximately 12–25% savings in maintenance cost (Kuş et al., 2023). In a "
"sector where maintenance can reach up to 60% of total production cost, these figures translate directly "
"into profit.")
pdf.kpi([("30–50%", "Potential reduction in\nunplanned downtime"),
         ("18–25%", "Potential reduction in\nmaintenance cost"),
         ("MTTR ↓", "Repair time shortened by\nthe technical assistant"),
         ("Safety ↑", "Failures caught before\nthey become accidents")])
pdf.p("Beyond the economic benefit there are two further contributions. On occupational health and safety, "
"sudden brake, hydraulic or engine failures are caught before they turn into a physical accident, and "
"emergency intervention in confined, hazardous environments is replaced by planned maintenance under "
"controlled conditions. On the environmental side, motor current analysis supports energy efficiency, "
"while avoiding unnecessary part replacement reduces waste generation and the carbon footprint.")
pdf.gorsel(os.path.join(SEMA, "surdurulebilirlik.png"),
           "Figure 11. Sustainability dimensions: financial, environmental and social/safety contributions.",
           genislik=150)

# ─────────────────────────── 12 ───────────────────────────
pdf.h1("12", "Feasibility and Roadmap")
pdf.p("The methods used (Isolation Forest, LSTM, vector-based RAG) are mature, validated algorithms in "
"both industry and academia, which lowers the technical risk of the solution. The system is designed to "
"operate across different equipment brands and models without architectural change. Telemetry from "
"existing PLC/SCADA infrastructure can be integrated over the Modbus and MQTT industrial protocols.")
pdf.gorsel(os.path.join(SEMA, "yol_haritasi.png"),
           "Figure 12. Maturity and commercialisation roadmap: working prototype, field pilot, "
           "productisation and scale-up phases.", genislik=160)
pdf.h2("12.1  Next steps")
pdf.tablo(["Phase", "Scope", "Output"],
    [["Field pilot", "Real sensor integration on 2–3 machines at a single operation; retraining the models on site data",
      "Model performance validated on real data"],
     ["Service manual ingestion", "Full ingestion of manufacturer maintenance manuals into the vector database",
      "A technical assistant covering thousands of pages"],
     ["Advanced embedding model", "Migration to newer open-source embedding models with higher retrieval performance",
      "More accurate document retrieval, still at zero licence cost"],
     ["3D digital twin", "Three-dimensional, component-level visualisation of the failure",
      "A clearer failure representation for the operator"],
     ["Productisation", "Multi-tenant structure, role-based access control, monitoring at scale",
      "A product deployable across multiple operations"]],
    [46, 84, 50])
pdf.p("Table 9. Commercialisation roadmap and next steps.", 7.4)
pdf.h2("12.2  Risks and mitigation")
pdf.tablo(["Risk", "Mitigation approach"],
    [["Difficulty accessing real field data", "Development on a physics-based simulator; pilot partnerships; gradual retraining on data collected from the site"],
     ["Resistance to adopting new software", "Parallel deployment over standard protocols without touching existing SCADA/PLC infrastructure"],
     ["Cyber security of critical infrastructure", "Fully on-premise deployment; no external service dependency; data never leaves the operation"],
     ["Risk of model false alarms", "Consecutive-confirmation rule and per-machine calibration; measured false alarm rate of 0.00%"]],
    [56, 124])
pdf.p("Table 10. Principal risks and mitigation approaches.", 7.4)

# ─────────────────────────── 13 ───────────────────────────
pdf.h1("13", "Project Team and Contact")
pdf.p("The project is carried out under the name ÇankaYazılım. The system architecture, AI layer, backend "
"services, data infrastructure and user interface were developed end to end and validated in working "
"condition. The project reached the semi-final of the TEKNOFEST 2026 Mining Technologies Competition.")
pdf.kutu("Contact",
"Muhammed Hamza KARAMANLI — Team Lead and Project Manager\n"
"E-mail: hamzakaramanli33@gmail.com  ·  hamzakaramanli2011@outlook.com\n"
f"Source code and technical documentation: {GITHUB}", PRIMARY)
pdf.p("For pilot deployments, technology partnerships or a detailed technical evaluation, please get in "
"touch at the addresses above. A live demonstration of the system can be provided on request.")

# ─────────────────────────── 14 ───────────────────────────
pdf.h1("14", "References")
pdf.p("The principal sources cited in this report are listed with full bibliographic details in Table 1. "
"The following institutional sources were also used:", 9)
pdf.madde([
"McKinsey & Company (2020). Analytics-driven maintenance technologies. — Figures on the effect of "
"predictive maintenance on downtime and cost.",
"CDC / NIOSH (2024). Machinery- and haulage-related mining fatalities. — Equipment-related fatality rates "
"in mining accidents.",
"MSHA — Mine Safety and Health Administration (2021). Final accident report, 22 February 2021. — Fatal "
"accident caused by brake failure.",
"Sandvik technical product documentation — Real equipment operating ranges used in the simulator.",
])

pdf.output(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "CankaYazilim_Technical_Commercial_Report_EN.pdf"))
print("✅ EN report generated:", pdf.page_no(), "pages")
