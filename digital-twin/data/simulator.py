"""
Dijital İkiz Simülatörü v2 — Sandvik LH517i / TH551i
═════════════════════════════════════════════════════

v1'den farkı (neden yeniden yazıldı?)
─────────────────────────────────────
v1'de her okuma "fazın sabit değeri + bağımsız gürültü" idi: makinenin bir
önceki saniyesiyle bir sonraki arasında fiziksel bağ yoktu, arızalar 3-4
okumalık basamak olarak enjekte edilip kayboluyordu, yıpranma ise canlı
akışta görünmeyecek kadar yavaştı. Böyle bir veriden LSTM'in öğrenebileceği
bir dinamik yoktu.

v2 üç fiziksel katmandan oluşur ve CANLI akış ile EĞİTİM verisi AYNI motoru
kullanır (eğitim/servis uyumsuzluğu yok):

 1) OPERASYON DÖNGÜSÜ (saniye ölçeği)
    LHD / kamyon döngüsü fazlar halinde ilerler; faz süreleri her döngüde
    ±%20 değişir. Faz yalnız "komut"u (gaz, yük, hedef hız, hidrolik) belirler;
    sensörler bu komuta birinci mertebe gecikmeyle (zaman sabitleriyle) yaklaşır.

 2) FİZİKSEL DİNAMİK (saniye ölçeği)
    • Sıcaklık: toplu ısıl kapasite modeli  dT/dt = (T_denge - T) / τ,
      τ ≈ 4 dk. Isı üretimi yakıt/yükle, soğutma verimi radyatör durumuyla
      belirlenir. Yokuşta sıcaklık bir anda zıplamaz, dakikalar içinde tırmanır.
    • Devir, hız, tork, akım, basınç: kendi zaman sabitleriyle komutu izler.
    • Titreşim: motor devri + yük + zemin pürüzlülüğü (Ornstein-Uhlenbeck
      süreci) + bileşen hasarından gelen katkılar.
    • Ölçüm gürültüsü: sensör başına beyaz gürültü.

 3) BİLEŞEN HASARI (çalışma-saati ölçeği)
    8 bileşenin her biri için hasar D ∈ [0, 1]:
      • Kuluçka: bileşen bir süre sağlam kalır; hasarın başlama anı
        Weibull dağılımından çekilir (bileşen başına ölçek η).
      • Büyüme: başladıktan sonra  dD/dh = g · s(t) · (D + 0.05)
        (yük/strese bağlı, kendini hızlandıran büyüme — çatlak/aşınma
        literatüründeki üstel ilerlemenin basit biçimi). g makine başına
        log-normal → her makine farklı hızda bozulur.
      • D = 1 → bileşen arızalandı (tanım gereği; sensör eşiğinden bağımsız).
    Hasar sensörlere fiziksel kanaldan yansır: rulman → titreşim (devirle
    büyür), pompa → basınç kaybı, radyatör → soğutma verimi düşer, enjektör →
    yakıt artar / tork düşer / ateşleme kaçırma titreşimi ...

İKİ SAAT: Hasar saati, fiziksel saate göre AGING_ACCEL kat hızlı akar
(varsayılan 600: 1 gerçek saniye = 10 dk çalışma). Böylece canlı demoda
yüzlerce saatlik bir bozulma ~15 dakikada izlenebilir. Okumalardaki
`op_hours` (motor saat sayacı — gerçek makinelerde de standart bir
telemetri alanıdır) hasar saatini taşır. Değer SIM_AGING_ACCEL ortam
değişkeniyle değiştirilebilir; 1 = gerçek zaman.

Gerçek RUL (kalan faydalı ömür) simülatörde BİLİNİR: hasar modelinden
analitik olarak hesaplanır. Bu, modellerin dürüstçe ölçülebilmesini sağlar
(`ground_truth()`); modellere girdi olarak VERİLMEZ.
"""

from __future__ import annotations

import copy
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# ═════════════════════════════════════════════════════════════════════════
# 1) EKİPMAN PROFİLLERİ — Sandvik teknik dokümantasyonu (normal çalışma bandı)
# ═════════════════════════════════════════════════════════════════════════
_LOADER = {
    "type": "loader", "model": "Sandvik LH517i",
    "temperature": (72, 88),    # °C — motor/hidrolik yağ
    "vibration":   (0.8, 4.5),  # mm/s RMS
    "pressure":    (250, 280),  # bar — hidrolik
    "current":     (150, 195),  # A — sürücü motor
    "speed":       (1.0, 7.0),  # km/h
    "gas":         (0.1, 0.6),  # % CH4
    "rpm":         (800, 2100),
    "torque":      (300, 2300),
    "fuel":        (8, 52),
}
EQUIPMENT_PROFILES: Dict[str, dict] = {
    "LH517i_001": {**_LOADER, "label": "LH517i #1 — Yükleyici"},
    "LH517i_002": {**_LOADER, "label": "LH517i #2 — Yükleyici"},
    "TH551i_001": {
        "type": "truck", "model": "Sandvik TH551i", "label": "TH551i #1 — Kamyon",
        "temperature": (75, 92),
        "vibration":   (1.0, 5.0),
        "pressure":    (200, 250),
        "current":     (180, 220),
        "speed":       (2.0, 30.0),
        "gas":         (0.1, 0.6),
        "rpm":         (800, 2100),
        "torque":      (400, 2600),
        "fuel":        (10, 62),
    },
}

SENSORS = ["temperature", "vibration", "pressure", "current", "speed",
           "rpm", "torque", "fuel", "gas"]

AGING_ACCEL = float(os.getenv("SIM_AGING_ACCEL", "600"))
NATURAL_FAULTS = os.getenv("SIM_NATURAL_FAULTS", "1") != "0"
T_AMBIENT = 28.0        # °C — yer altı ortam sıcaklığı
TAU_TEMP = 240.0        # s — motor/yağ ısıl zaman sabiti
FAIL_DOWNTIME_S = 45.0  # s — arıza sonrası makinenin durduğu süre (canlı)

# ═════════════════════════════════════════════════════════════════════════
# 2) METAN (CH4) — İSG eşikleri (ML'den bağımsız, mutlak)
# ═════════════════════════════════════════════════════════════════════════
METHANE_LIMITS = {"uyari": 1.0, "tehlike": 1.5, "kritik": 2.0}


def gas_status(gas_pct: float) -> dict:
    if gas_pct >= METHANE_LIMITS["kritik"]:
        return {"seviye": "KRİTİK", "renk": "kirmizi",
                "mesaj": f"TAHLİYE — Metan %{gas_pct:.2f} (patlama riski). Tüm personel tahliye edilmeli."}
    if gas_pct >= METHANE_LIMITS["tehlike"]:
        return {"seviye": "TEHLİKE", "renk": "turuncu",
                "mesaj": f"Metan %{gas_pct:.2f} — Elektrikli ekipmanı durdurun, havalandırmayı artırın."}
    if gas_pct >= METHANE_LIMITS["uyari"]:
        return {"seviye": "UYARI", "renk": "sari",
                "mesaj": f"Metan %{gas_pct:.2f} — Eşik aşıldı, havalandırma kontrol edilmeli."}
    return {"seviye": "NORMAL", "renk": "yesil", "mesaj": f"Metan %{gas_pct:.2f} — Güvenli aralık."}


# ═════════════════════════════════════════════════════════════════════════
# 3) OPERASYON DÖNGÜSÜ
# ═════════════════════════════════════════════════════════════════════════
LHD_CYCLE: List[Tuple[str, int]] = [
    ("idle", 5), ("approach_pile", 8), ("picking_up", 10), ("hauling_loaded", 30),
    ("approach_dump", 10), ("dumping", 6), ("returning_empty", 25),
]
TRUCK_CYCLE: List[Tuple[str, int]] = [
    ("idle_waiting", 12), ("getting_loaded", 20), ("accelerating_loaded", 10),
    ("climbing_loaded", 45), ("arriving_dump", 10), ("dumping", 6),
    ("descending_empty", 35), ("accelerating_empty", 8),
]


def _cycle_for(eq_type: str) -> List[Tuple[str, int]]:
    return TRUCK_CYCLE if eq_type == "truck" else LHD_CYCLE


# Faz komutları: load (0-1), throttle (0-1), vib (zemin/aksiyon çarpanı),
# speed (hız bandında oran; 0 = dur), spike (hidrolik tepe), cooling (iniş)
PHASE_PROFILES: Dict[str, dict] = {
    "idle":                {"load": 0.0, "throttle": 0.10, "vibration_mult": 0.4,  "speed_mult": 0.0},
    "approach_pile":       {"load": 0.0, "throttle": 0.50, "vibration_mult": 0.7,  "speed_mult": 0.7},
    "picking_up":          {"load": 0.7, "throttle": 0.90, "vibration_mult": 1.6,  "speed_mult": 0.2, "pressure_spike": True},
    "hauling_loaded":      {"load": 1.0, "throttle": 0.85, "vibration_mult": 1.1,  "speed_mult": 0.5},
    "approach_dump":       {"load": 1.0, "throttle": 0.30, "vibration_mult": 0.8,  "speed_mult": 0.4},
    "dumping":             {"load": 0.4, "throttle": 0.60, "vibration_mult": 1.4,  "speed_mult": 0.1, "pressure_spike": True},
    "returning_empty":     {"load": 0.0, "throttle": 0.65, "vibration_mult": 0.6,  "speed_mult": 0.9},
    "idle_waiting":        {"load": 0.0, "throttle": 0.10, "vibration_mult": 0.35, "speed_mult": 0.0},
    "getting_loaded":      {"load": 0.6, "throttle": 0.20, "vibration_mult": 1.5,  "speed_mult": 0.0},
    "accelerating_loaded": {"load": 1.0, "throttle": 1.00, "vibration_mult": 1.2,  "speed_mult": 0.4},
    "climbing_loaded":     {"load": 1.0, "throttle": 1.00, "vibration_mult": 1.0,  "speed_mult": 0.25},
    "arriving_dump":       {"load": 1.0, "throttle": 0.30, "vibration_mult": 0.7,  "speed_mult": 0.5},
    "descending_empty":    {"load": 0.0, "throttle": 0.30, "vibration_mult": 0.5,  "speed_mult": 0.85, "cooling": True},
    "accelerating_empty":  {"load": 0.0, "throttle": 0.80, "vibration_mult": 0.7,  "speed_mult": 0.9},
    # Manuel koşul (döngüde yok): bozuk/taşlık zeminde yüklü ilerleme — NORMAL çalışma.
    "kotu_yol":            {"load": 0.8, "throttle": 0.95, "vibration_mult": 1.9,  "speed_mult": 0.25},
}
ALL_PHASES = list(PHASE_PROFILES)
_PH = {k: np.array([PHASE_PROFILES[p].get(k, d) for p in ALL_PHASES], dtype=float)
       for k, d in (("load", 0.0), ("throttle", 0.5), ("vibration_mult", 1.0),
                    ("speed_mult", 0.5), ("pressure_spike", 0.0), ("cooling", 0.0))}

MANUAL_SCENARIOS: Dict[str, List[Tuple[str, str]]] = {
    "loader": [
        ("idle", "Rölanti — bekleme"),
        ("returning_empty", "Boş — düz yol (hızlı)"),
        ("picking_up", "Kepçe doldurma (hidrolik yük)"),
        ("hauling_loaded", "Yüklü — taşıma"),
        ("kotu_yol", "Kötü / taşlık yol — yüklü"),
    ],
    "truck": [
        ("idle_waiting", "Rölanti — bekleme"),
        ("descending_empty", "Boş — yokuş aşağı (serin, hızlı)"),
        ("accelerating_loaded", "Yüklü — düz yol"),
        ("climbing_loaded", "Yüklü — yokuş yukarı (max stres)"),
        ("kotu_yol", "Kötü / taşlık yol — yüklü"),
    ],
}


def manual_scenarios_for(eq_type: str) -> List[Tuple[str, str]]:
    return MANUAL_SCENARIOS.get(eq_type, MANUAL_SCENARIOS["loader"])


# ═════════════════════════════════════════════════════════════════════════
# 4) BİLEŞENLER — hasar süreçleri
# ═════════════════════════════════════════════════════════════════════════
# eta: hasar başlangıcı Weibull ölçeği (çalışma saati), beta: şekil
# g: başladıktan sonra büyüme hızı medyanı (1/saat); D'nin 0→1 süresi ≈ ln(21)/g
COMPONENTS: Dict[str, dict] = {
    "rulman":         {"eta": 3500, "g": 0.020, "ad": "Rulman aşınması",
                       "sistem": "Tahrik/şasi — rulman", "sensor": "vibration",
                       "gerekce": "Titreşim, aynı devir ve yükte beklenenin belirgin üzerinde; devirle birlikte büyüyor (rulman yüzey hasarı imzası)."},
    "hidrolik_pompa": {"eta": 4000, "g": 0.022, "ad": "Hidrolik/yağ pompası arızası",
                       "sistem": "Hidrolik sistem — pompa", "sensor": "pressure",
                       "gerekce": "Hidrolik basınç, aynı çalışma koşulunda beklenenin altında; pompa basıncı koruyamıyor."},
    "sogutma":        {"eta": 4500, "g": 0.018, "ad": "Soğutma sistemi arızası",
                       "sistem": "Soğutma — radyatör/fan", "sensor": "temperature",
                       "gerekce": "Motor sıcaklığı, mevcut yük geçmişine göre beklenenin üzerinde; soğutma verimi düşüyor."},
    "motor_isi":      {"eta": 5000, "g": 0.020, "ad": "Motor aşırı ısınması",
                       "sistem": "Motor — iç sürtünme/yağlama", "sensor": "temperature",
                       "gerekce": "Isı üretimi artıyor; aynı yakıt/yükte motor daha sıcak çalışıyor."},
    "enjektor":       {"eta": 4500, "g": 0.020, "ad": "Enjektör / yanma arızası",
                       "sistem": "Güç aktarma — yakıt/enjektör", "sensor": "fuel",
                       "gerekce": "Aynı tork için yakıt tüketimi artıyor ve düzensiz yanma titreşimi görülüyor."},
    "motor_sargi":    {"eta": 5500, "g": 0.019, "ad": "Aşırı akım — motor sargı zorlanması",
                       "sistem": "Tahrik motoru — sargı", "sensor": "current",
                       "gerekce": "Sürücü motor akımı aynı yükte beklenenin üzerinde; sargı izolasyonu zayıflıyor."},
    "fren":           {"eta": 4000, "g": 0.024, "ad": "Fren sistemi sürtmesi / aşırı ısınma",
                       "sistem": "Fren sistemi", "sensor": "temperature",
                       "gerekce": "Fren sürtmesi: hız düşük, tork ve sıcaklık yüksek, titreşim hızla artıyor — İSG riski."},
    "transmisyon":    {"eta": 5000, "g": 0.018, "ad": "Transmisyon / güç aktarma arızası",
                       "sistem": "Güç aktarma — şanzıman", "sensor": "vibration",
                       "gerekce": "Dişli kavrama titreşimi ve yağ sıcaklığı yükseliyor; dişli/rulman aşınması gelişiyor."},
}
COMPONENT_NAMES = list(COMPONENTS)
_CI = {c: i for i, c in enumerate(COMPONENT_NAMES)}
WEIBULL_BETA = 1.4
GROWTH_SIGMA = 0.30          # g'nin log-normal yayılımı
D_OFFSET = 0.05
INJECT_D = 0.15              # Canlı Test: başlatılan arızanın başlangıç hasarı

# Arayüz/eski API arıza kodları → bileşen
FAULT_ALIASES = {
    "yag_pompasi": "hidrolik_pompa", "pump": "hidrolik_pompa", "pressure_surge": "hidrolik_pompa",
    "rulman": "rulman", "vibration_spike": "rulman",
    "overheat": "motor_isi", "sogutma": "sogutma", "cooling": "sogutma",
    "enjektor": "enjektor", "injector": "enjektor",
    "overcurrent": "motor_sargi", "fren": "fren",
    "transmisyon": "transmisyon", "sanziman": "transmisyon",
}

# Kritik sensör eşikleri — yalnız açıklama metinleri için (arıza tanımı D=1'dir)
CRITICAL_MULTIPLIERS = {"temperature": 1.45, "vibration": 2.8, "current": 1.6, "pressure": 1.7}


def critical_thresholds(equipment_id: str) -> dict:
    p = EQUIPMENT_PROFILES[equipment_id]
    return {k: round(p[k][1] * m, 2) for k, m in CRITICAL_MULTIPLIERS.items()}


def _stress_avg(eq_type: str) -> np.ndarray:
    """Döngü boyunca ortalama stres (gerçek RUL hesabı için) — bileşen başına."""
    cyc = _cycle_for(eq_type)
    w = np.array([d for _, d in cyc], float)
    L = np.array([PHASE_PROFILES[p]["load"] for p, _ in cyc])
    u = np.array([PHASE_PROFILES[p]["throttle"] for p, _ in cyc])
    lm, um = (w * L).sum() / w.sum(), (w * u).sum() / w.sum()
    return _stress(np.array([lm]), np.array([um]))[0]


def _stress(load: np.ndarray, rpm_frac: np.ndarray) -> np.ndarray:
    """Bileşen başına anlık stres çarpanı, şekil (n, C)."""
    base = 0.6 + 0.8 * load
    s = np.repeat(base[:, None], len(COMPONENT_NAMES), axis=1)
    for c in ("rulman", "transmisyon"):
        s[:, _CI[c]] += 0.3 * rpm_frac
    s[:, _CI["fren"]] += 0.3 * load
    return s


# ═════════════════════════════════════════════════════════════════════════
# 5) SİMÜLASYON MOTORU — N makine birlikte (vektörel); canlıda N=1
# ═════════════════════════════════════════════════════════════════════════
class Fleet:
    """Aynı ekipman tipinden N makinenin fiziksel dijital ikizi.

    step(dt) fiziksel saati dt saniye ilerletir; read() o anki sensör
    okumalarını (ölçüm gürültüsüyle) döner. Canlı akış (generate_reading)
    ve eğitim verisi (simulate_streams) bu sınıfı birebir aynı şekilde kullanır.
    """

    def __init__(self, equipment_id: str, n: int = 1, seed: Optional[int] = None,
                 aging_accel: float = AGING_ACCEL, natural_faults: bool = True,
                 op_hours: Optional[np.ndarray] = None):
        self.eq_id = equipment_id
        self.prof = EQUIPMENT_PROFILES[equipment_id]
        self.type = self.prof["type"]
        self.n = n
        self.rng = np.random.default_rng(seed)
        self.accel = aging_accel
        self.natural = natural_faults
        rng = self.rng

        cyc = _cycle_for(self.type)
        self.cycle_idx = np.array([ALL_PHASES.index(p) for p, _ in cyc])
        self.cycle_dur = np.array([d for _, d in cyc], float)
        self.cpos = rng.integers(0, len(cyc), n)                 # döngüdeki konum
        self.pdur = self.cycle_dur[self.cpos] * rng.uniform(0.8, 1.2, n)
        self.pel = rng.uniform(0, 1, n) * self.pdur              # fazda geçen süre
        self.manual = np.full(n, -1)                             # -1 = otomatik döngü
        self.down_s = np.zeros(n)                                # arıza sonrası duruş

        p = self.prof
        self.load = np.zeros(n)
        self.rpm = np.full(n, float(p["rpm"][0]))
        self.speed = np.zeros(n)
        self.torque = np.full(n, p["torque"][0] * 0.03)
        self.fuel = np.full(n, float(p["fuel"][0]))
        self.current = np.full(n, float(p["current"][0]))
        self.pressure = np.full(n, float(np.mean(p["pressure"])))
        t_lo, t_hi = p["temperature"]
        self.temp = rng.uniform(t_lo, t_lo + 0.6 * (t_hi - t_lo), n)
        self.vib = np.full(n, float(p["vibration"][0]))
        self.road = np.zeros(n)
        g_lo, g_hi = p["gas"]
        self.gas = np.full(n, (g_lo + g_hi) / 2)
        self.gas_event = np.zeros(n)

        self.op_hours = (np.asarray(op_hours, float) if op_hours is not None
                         else rng.uniform(150, 800, n))
        C = len(COMPONENT_NAMES)
        self.D = np.zeros((n, C))
        self.g = np.array([COMPONENTS[c]["g"] for c in COMPONENT_NAMES])[None, :] \
            * rng.lognormal(0.0, GROWTH_SIGMA, (n, C))
        self.onset = np.full((n, C), np.inf)
        if natural_faults:
            self.onset = self.op_hours[:, None] + self._sample_incubation((n, C))
        self.failures: List[dict] = []
        self.s_avg = _stress_avg(self.type)

        # Makineden makineye fark (üretim toleransı, saha koşulu, sensör
        # kalibrasyonu): her birim kendi sabit sapmalarıyla gelir. Normal
        # davranış modeli bunları bilmez → artıklarda gerçekçi bir taban
        # belirsizliği oluşur (tüm makineler birebir aynı olsaydı tespit
        # yapay biçimde kolaylaşırdı).
        v = lambda s: 1.0 + rng.normal(0, s, n)
        self.var = {"heat": v(0.03), "cool": v(0.03), "amb": rng.normal(0, 2.0, n),
                    "vib": v(0.08), "pres": v(0.015), "cur": v(0.02), "fuel": v(0.03),
                    "t_bias": rng.normal(0, 0.8, n), "p_bias": rng.normal(0, 2.0, n)}

    # ── yardımcılar ──────────────────────────────────────────────
    def _sample_incubation(self, shape):
        eta = np.array([COMPONENTS[c]["eta"] for c in COMPONENT_NAMES], float)
        return eta * self.rng.weibull(WEIBULL_BETA, shape)

    def repair(self, unit: int = 0, component: Optional[str] = None) -> List[str]:
        """Bakım: bileşen(ler)i yenile (hasar 0, yeni kuluçka)."""
        idx = range(len(COMPONENT_NAMES)) if component is None else [_CI[component]]
        done = []
        for ci in idx:
            name = COMPONENT_NAMES[ci]
            if self.D[unit, ci] > 0:
                done.append(name)
            self.D[unit, ci] = 0.0
            self.g[unit, ci] = COMPONENTS[name]["g"] * self.rng.lognormal(0, GROWTH_SIGMA)
            self.onset[unit, ci] = (self.op_hours[unit]
                                    + COMPONENTS[name]["eta"] * self.rng.weibull(WEIBULL_BETA)
                                    if self.natural else np.inf)
        return done

    def start_fault(self, component: str, unit: int = 0, d0: float = INJECT_D):
        """Canlı Test: bileşende hasarı ŞİMDİ başlat (kuluçkayı atla). Hasar
        bundan sonra fiziksel modelle büyümeye devam eder — kendiliğinden
        kaybolmaz; bakım (repair) ya da arıza ile sonlanır."""
        ci = _CI[component]
        self.onset[unit, ci] = min(self.onset[unit, ci], self.op_hours[unit])
        self.D[unit, ci] = max(self.D[unit, ci], d0)

    def phase_names(self) -> List[str]:
        return [ALL_PHASES[i] for i in self._phase_idx()]

    def _phase_idx(self) -> np.ndarray:
        idx = self.cycle_idx[self.cpos]
        idx = np.where(self.manual >= 0, self.manual, idx)
        if self.down_s.any():
            idle = ALL_PHASES.index("idle_waiting" if self.type == "truck" else "idle")
            idx = np.where(self.down_s > 0, idle, idx)
        return idx

    def true_rul(self) -> Tuple[np.ndarray, np.ndarray]:
        """Analitik gerçek RUL (saat) ve onu belirleyen bileşen indeksi."""
        gs = self.g * self.s_avg[None, :]
        active = self.op_hours[:, None] >= self.onset
        t_grow = np.log((1 + D_OFFSET) / (self.D + D_OFFSET)) / gs
        t_full = np.log((1 + D_OFFSET) / D_OFFSET) / gs
        rul_c = np.where(self.D >= 1, 0.0,
                         np.where(active, t_grow, (self.onset - self.op_hours[:, None]) + t_full))
        ci = np.argmin(rul_c, axis=1)
        return rul_c[np.arange(self.n), ci], ci

    # ── fiziksel adım ────────────────────────────────────────────
    def step(self, dt: float = 1.0):
        n, p, rng = self.n, self.prof, self.rng
        a = lambda tau: 1.0 - np.exp(-dt / tau)

        # Faz ilerlemesi (manuel ve duruşta olmayanlar)
        run = (self.manual < 0) & (self.down_s <= 0)
        self.pel = np.where(run, self.pel + dt, self.pel)
        nxt = run & (self.pel >= self.pdur)
        if nxt.any():
            self.pel[nxt] -= self.pdur[nxt]
            self.cpos[nxt] = (self.cpos[nxt] + 1) % len(self.cycle_idx)
            self.pdur[nxt] = self.cycle_dur[self.cpos[nxt]] * rng.uniform(0.8, 1.2, nxt.sum())
        self.down_s = np.maximum(0.0, self.down_s - dt)

        ph = self._phase_idx()
        L_t, u = _PH["load"][ph], _PH["throttle"][ph]
        vmul, smul = _PH["vibration_mult"][ph], _PH["speed_mult"][ph]
        spike, cool = _PH["pressure_spike"][ph] > 0, _PH["cooling"][ph] > 0
        D = self.D
        d = {c: D[:, i] for c, i in _CI.items()}

        # Yük, devir, hız
        self.load += a(3.0) * (L_t - self.load)
        r_lo, r_hi = p["rpm"]
        self.rpm += a(1.5) * (r_lo + (r_hi - r_lo) * u - self.rpm)
        rf = np.clip((self.rpm - r_lo) / (r_hi - r_lo), 0, 1)
        s_lo, s_hi = p["speed"]
        spd_t = np.where(smul > 0, s_lo + smul * (s_hi - s_lo), 0.0) * (1 - 0.45 * d["fren"])
        self.speed += a(7.0 if self.type == "truck" else 4.0) * (spd_t - self.speed)

        # Tork (iniş: motor freni; rölanti: ~0; fren sürtmesi: ek tork; enjektör: kayıp)
        tq_lo, tq_hi = p["torque"]
        tq_t = tq_lo + (tq_hi - tq_lo) * np.clip(0.55 * self.load + 0.45 * u, 0, 1)
        tq_t = np.where(cool, tq_t * 0.35, tq_t)
        idle = (smul <= 0) & (L_t <= 0) & (u <= 0.15)
        tq_t = np.where(idle, tq_lo * 0.03, tq_t)
        tq_t = tq_t * (1 - 0.30 * d["enjektor"]) * (1 + 0.25 * d["fren"] * (smul > 0))
        self.torque += a(0.8) * (tq_t - self.torque)

        # Yakıt
        f_lo, f_hi = p["fuel"]
        heat_frac = np.clip(0.6 * u + 0.35 * self.load, 0, 1)
        fuel_t = (f_lo + (f_hi - f_lo) * heat_frac) \
            * (1 + 0.35 * d["enjektor"] + 0.10 * d["hidrolik_pompa"] + 0.10 * d["fren"]) \
            * self.var["fuel"]
        self.fuel += a(1.0) * (fuel_t - self.fuel)

        # Akım (sürücü motor) — sargı hasarı akımı yükseltir
        c_lo, c_hi = p["current"]
        cur_t = (c_lo + (c_hi - c_lo) * (0.05 + 0.55 * u + 0.35 * self.load)) \
            * (1 + 0.60 * d["motor_sargi"]) * self.var["cur"]
        self.current += a(0.5) * (cur_t - self.current)

        # Hidrolik basınç — pompa hasarı basıncı düşürür
        pr_lo, pr_hi = p["pressure"]
        p_t = np.where(spike, pr_hi + 0.1 * (pr_hi - pr_lo), pr_lo + 0.5 * (pr_hi - pr_lo))
        p_t = p_t * (1 - 0.55 * d["hidrolik_pompa"]) * self.var["pres"]
        self.pressure += a(0.8) * (p_t - self.pressure)

        # Sıcaklık — toplu ısıl model
        t_lo, t_hi = p["temperature"]
        G = (t_lo - T_AMBIENT) + (t_hi - t_lo) * (0.1 + 0.8 * heat_frac)
        G = G * (1 + 0.75 * d["motor_isi"] + 0.35 * d["fren"] + 0.25 * d["transmisyon"]
                 + 0.12 * d["rulman"] + 0.20 * d["motor_sargi"] + 0.10 * d["enjektor"]) \
            * self.var["heat"]
        kc = (1 - 0.5 * d["sogutma"]) * np.where(cool, 1.25, 1.0) * self.var["cool"]
        self.temp += a(TAU_TEMP) * (T_AMBIENT + self.var["amb"] + G / kc - self.temp)

        # Titreşim (RMS) — zemin pürüzü OU süreci + hasar katkıları
        self.road += -self.road * dt / 3.0 + np.sqrt(2 * dt / 3.0) * rng.standard_normal(n)
        v_lo, v_hi = p["vibration"]
        vr = v_hi - v_lo
        sf = np.clip(self.speed / s_hi, 0, 1)
        v = (v_lo + vr * (0.12 + 0.28 * rf + 0.12 * self.load
                          + 0.30 * np.maximum(0, vmul - 1))) * self.var["vib"]
        v += vr * 0.10 * sf * np.abs(self.road) * vmul
        v += vr * 2.2 * d["rulman"] ** 1.5 * (0.5 + 0.5 * rf)
        v += vr * 1.5 * d["transmisyon"] ** 1.5 * (0.3 + 0.7 * rf)
        misfire = rng.random(n) < 0.5 * d["enjektor"]
        v += vr * d["enjektor"] * (0.6 + 1.2 * misfire)
        v += vr * (0.5 * d["hidrolik_pompa"] + 0.8 * d["fren"] * sf)
        self.vib += a(1.0) * (v - self.vib)

        # Metan — ortam OU süreci + dışarıdan tetiklenen gaz olayı (sönümlenir)
        g_lo, g_hi = p["gas"]
        gm = (g_lo + g_hi) / 2
        self.gas += (gm - self.gas) * dt / 120.0 + 0.04 * np.sqrt(dt / 60.0) * rng.standard_normal(n)
        self.gas = np.maximum(0.0, self.gas)
        self.gas_event *= np.exp(-dt / 40.0)

        # Hasar büyümesi (hasar saati)
        dt_h = dt * self.accel / 3600.0
        if dt_h > 0:
            active = self.op_hours[:, None] >= self.onset
            s = _stress(self.load, rf)
            self.D = np.where(active, np.minimum(1.0, D + self.g * s * (D + D_OFFSET) * dt_h), D)
            self.op_hours = self.op_hours + dt_h * (self.down_s <= 0)
            newly = (self.D >= 1.0) & (D < 1.0)
            if newly.any():
                for i, ci in zip(*np.nonzero(newly)):
                    self.failures.append({"unit": int(i), "component": COMPONENT_NAMES[ci],
                                          "op_hours": float(self.op_hours[i])})

    def read(self) -> Dict[str, np.ndarray]:
        """Ölçüm gürültülü sensör okumaları (her anahtar şekil (n,))."""
        rng, n, p = self.rng, self.n, self.prof
        nz = lambda s: rng.normal(0, s, n)
        speed = np.where(self.speed < 0.05, 0.0, np.maximum(0, self.speed + nz(0.03 * p["speed"][1] / 7)))
        return {
            "temperature": self.temp + self.var["t_bias"] + nz(0.25),
            "vibration":   np.maximum(0.05, self.vib * (1 + nz(0.03)) + nz(0.03)),
            "pressure":    self.pressure + self.var["p_bias"] + nz(1.2),
            "current":     self.current + nz(1.2),
            "speed":       speed,
            "rpm":         np.maximum(0, self.rpm + nz(8.0)),
            "torque":      np.maximum(0, self.torque * (1 + nz(0.015)) + nz(3.0)),
            "fuel":        np.maximum(0, self.fuel + nz(0.4)),
            "gas":         np.maximum(0, self.gas + self.gas_event + nz(0.01)),
        }


# ═════════════════════════════════════════════════════════════════════════
# 6) CANLI DİJİTAL İKİZ — makine başına tekil durum
# ═════════════════════════════════════════════════════════════════════════
_twins: Dict[str, Fleet] = {}
_last_update: Dict[str, datetime] = {}
_events: Dict[str, List[dict]] = {}


def get_twin(equipment_id: str) -> Fleet:
    if equipment_id not in _twins:
        tw = Fleet(equipment_id, n=1, natural_faults=NATURAL_FAULTS)
        # Isıl durumu dengeye oturt (soğuk başlangıç geçişi canlıya taşınmasın)
        acc = tw.accel
        tw.accel = 0.0
        for _ in range(600):
            tw.step(1.0)
        tw.accel = acc
        _twins[equipment_id] = tw
        _events[equipment_id] = []
    return _twins[equipment_id]


class _StateView:
    """Geriye dönük uyumluluk: eski `_get_state(eq).manual_phase` kullanımı."""
    def __init__(self, tw: Fleet):
        self._tw = tw

    @property
    def manual_phase(self) -> Optional[str]:
        m = int(self._tw.manual[0])
        return None if m < 0 else ALL_PHASES[m]


def _get_state(equipment_id: str) -> _StateView:
    return _StateView(get_twin(equipment_id))


def set_manual_phase(equipment_id: str, phase) -> None:
    tw = get_twin(equipment_id)
    tw.manual[0] = -1 if phase in (None, "auto") else ALL_PHASES.index(phase)


def start_fault(equipment_id: str, fault_type: Optional[str] = None) -> str:
    tw = get_twin(equipment_id)
    comp = FAULT_ALIASES.get(fault_type, fault_type) if fault_type else None
    if comp not in COMPONENTS:
        comp = str(tw.rng.choice(COMPONENT_NAMES))
    tw.start_fault(comp)
    _events[equipment_id].append({"tip": "arıza_başlatıldı", "bilesen": comp,
                                  "op_hours": float(tw.op_hours[0]),
                                  "zaman": datetime.now(timezone.utc).isoformat()})
    return comp


def maintenance(equipment_id: str, component: Optional[str] = None) -> dict:
    tw = get_twin(equipment_id)
    comp = FAULT_ALIASES.get(component, component) if component else None
    yenilenen = tw.repair(0, comp)
    _events[equipment_id].append({"tip": "bakım", "bilesenler": yenilenen,
                                  "op_hours": float(tw.op_hours[0]),
                                  "zaman": datetime.now(timezone.utc).isoformat()})
    return {"equipment_id": equipment_id, "yenilenen": yenilenen}


def twin_status(equipment_id: str) -> dict:
    """İkizin iç durumu — hata ayıklama ve değerlendirme içindir (gerçek
    sahada bilinemeyecek değerleri, ör. gerçek RUL, içerir)."""
    tw = get_twin(equipment_id)
    rul, ci = tw.true_rul()
    return {
        "equipment_id": equipment_id,
        "op_hours": round(float(tw.op_hours[0]), 2),
        "faz": tw.phase_names()[0],
        "hasar": {c: round(float(tw.D[0, i]), 4) for c, i in _CI.items()},
        "gercek_rul_saat": round(float(rul[0]), 1),
        "belirleyici_bilesen": COMPONENT_NAMES[int(ci[0])],
        "yaslanma_hizlandirma": tw.accel,
        "olaylar": _events.get(equipment_id, [])[-20:],
    }


def _package(tw: Fleet, r: Dict[str, np.ndarray], i: int = 0) -> dict:
    out = {k: round(float(v[i]), 3) for k, v in r.items()}
    out["rpm"] = round(out["rpm"], 1)
    out["torque"] = round(out["torque"], 1)
    out["fuel"] = round(out["fuel"], 2)
    out["equipment_id"] = tw.eq_id
    out["equipment_type"] = tw.type
    out["phase"] = tw.phase_names()[i]
    out["op_hours"] = round(float(tw.op_hours[i]), 3)
    out["wear_level"] = round(float(tw.D[i].max()), 4)
    return out


def generate_reading(equipment_id: str, force_anomaly: bool = False,
                     force_gas: bool = False, fault_type: str = None) -> dict:
    """Canlı akış: ikizi geçen gerçek süre kadar ilerletip okuma döner.

    force_anomaly=True → bir bileşende arıza BAŞLATILIR (fault_type ile
    seçilebilir). Arıza tek okumada kaybolmaz; fiziksel olarak büyür.
    force_gas=True → ortamda metan olayı (birkaç dakikada sönümlenir)."""
    if equipment_id not in EQUIPMENT_PROFILES:
        equipment_id = next(iter(EQUIPMENT_PROFILES))
    tw = get_twin(equipment_id)

    now = datetime.now(timezone.utc)
    last = _last_update.get(equipment_id)
    dt = 3.0 if last is None else min(max((now - last).total_seconds(), 0.2), 30.0)
    _last_update[equipment_id] = now

    if force_anomaly:
        start_fault(equipment_id, fault_type)
    if force_gas:
        tw.gas_event[0] = float(tw.rng.uniform(1.2, 2.4))

    n_sub = int(np.ceil(dt))
    for _ in range(n_sub):
        tw.step(dt / n_sub)

    # Arıza (D=1) → makine durur; duruş sonrası düzeltici bakım
    while tw.failures:
        f = tw.failures.pop(0)
        tw.down_s[0] = FAIL_DOWNTIME_S
        _events[equipment_id].append({"tip": "ARIZA", "bilesen": f["component"],
                                      "op_hours": f["op_hours"], "zaman": now.isoformat()})
    if tw.down_s[0] > 0 and tw.down_s[0] <= dt + 1e-9:
        failed = [c for c, i in _CI.items() if tw.D[0, i] >= 1.0]
        for c in failed:
            tw.repair(0, c)
        if failed:
            _events[equipment_id].append({"tip": "düzeltici_bakım", "bilesenler": failed,
                                          "op_hours": float(tw.op_hours[0]),
                                          "zaman": now.isoformat()})
    return _package(tw, tw.read())


# ═════════════════════════════════════════════════════════════════════════
# 7) EĞİTİM / DEĞERLENDİRME VERİSİ — aynı motor, çok makine
# ═════════════════════════════════════════════════════════════════════════
STREAM_INTERVAL_S = 3.0   # canlı yayın aralığı (main.py) ile aynı


def simulate_streams(equipment_id: str, n_units: int, duration_s: float,
                     interval_s: float = STREAM_INTERVAL_S, seed: int = 0,
                     mode: str = "healthy", manual_prob: float = 0.25,
                     aging_accel: float = AGING_ACCEL, warmup_s: float = 600.0) -> dict:
    """N makinelik filo akışı üretir.

    mode:
      "healthy"         — hiç hasar başlamaz (normal davranış modeli/IF için)
      "run_to_failure"  — her makinede rastgele bir bileşen 0-150 saat içinde
                          bozulmaya başlar; makine ilk arızada durur (sonrası
                          maskelenir). Sınıflar dengeli olsun diye bileşen
                          makineler arasında sırayla dağıtılır.
      "natural"         — doğal kuluçka (canlı ikizle aynı)
    manual_prob: operatörün makineyi bir süre manuel koşulda (ör. kötü yol,
                 yokuş) tutma olasılığı — normal davranış çeşitliliği için.

    Dönüş: dict(X [n,T,S], op_hours, true_rul, true_comp, max_damage, phase, valid [n,T])
    """
    rng = np.random.default_rng(seed + 1000)
    tw = Fleet(equipment_id, n=n_units, seed=seed, aging_accel=aging_accel,
               natural_faults=(mode == "natural"))
    if mode == "run_to_failure":
        comps = (np.arange(n_units) + rng.integers(len(COMPONENT_NAMES))) % len(COMPONENT_NAMES)
        rng.shuffle(comps)
        tw.onset[:] = np.inf
        tw.onset[np.arange(n_units), comps] = tw.op_hours + rng.uniform(0, 150, n_units)

    acc = tw.accel
    tw.accel = 0.0
    for _ in range(int(warmup_s)):
        tw.step(1.0)
    tw.accel = acc

    man_choices = [ALL_PHASES.index(p) for p, _ in manual_scenarios_for(tw.type)]
    man_left = np.zeros(n_units)
    T = int(duration_s // interval_s)
    S = len(SENSORS)
    X = np.zeros((n_units, T, S), np.float32)
    oph = np.zeros((n_units, T), np.float32)
    rul = np.zeros((n_units, T), np.float32)
    comp = np.zeros((n_units, T), np.int16)
    dmax = np.zeros((n_units, T), np.float32)
    phase = np.zeros((n_units, T), np.int16)
    valid = np.ones((n_units, T), bool)
    alive = np.ones(n_units, bool)
    n_sub = int(np.ceil(interval_s))
    for t in range(T):
        # Operatör manuel koşul seçimi (normal çalışma çeşitliliği)
        if manual_prob > 0:
            start = (man_left <= 0) & (tw.manual >= 0)
            tw.manual[start] = -1
            pick = (tw.manual < 0) & (rng.random(n_units) < manual_prob * interval_s / 600.0)
            if pick.any():
                tw.manual[pick] = rng.choice(man_choices, pick.sum())
                man_left[pick] = rng.uniform(40, 240, pick.sum())
            man_left -= interval_s
        for _ in range(n_sub):
            tw.step(interval_s / n_sub)
        r = tw.read()
        X[:, t, :] = np.stack([r[k] for k in SENSORS], axis=1)
        oph[:, t] = tw.op_hours
        tr, tc = tw.true_rul()
        rul[:, t], comp[:, t] = tr, tc
        dmax[:, t] = tw.D.max(axis=1)
        phase[:, t] = tw._phase_idx()
        if mode == "run_to_failure":
            failed_now = tw.D.max(axis=1) >= 1.0
            valid[:, t] = alive
            alive &= ~failed_now
            if not alive.any():
                valid[:, t + 1:] = False
                X, oph, rul, comp, dmax, phase, valid = (a[:, :t + 1] for a in
                                                         (X, oph, rul, comp, dmax, phase, valid))
                break
    return {"X": X, "op_hours": oph, "true_rul": rul, "true_comp": comp,
            "max_damage": dmax, "phase": phase, "valid": valid, "sensors": SENSORS,
            "equipment_id": equipment_id, "interval_s": interval_s}


def generate_historical(hours: float = 24, interval_seconds: int = 30,
                        seed: int = 0) -> pd.DataFrame:
    """Geçmiş akış taklidi (seed.py) — her makine için ayrı ikiz, gerçek zaman."""
    rows = []
    now = datetime.now(timezone.utc)
    t0 = now - timedelta(hours=hours)
    steps = int(hours * 3600 // interval_seconds)
    for k, eq_id in enumerate(EQUIPMENT_PROFILES):
        tw = Fleet(eq_id, n=1, seed=seed + k, natural_faults=NATURAL_FAULTS)
        n_sub = int(np.ceil(interval_seconds))
        for s in range(steps):
            for _ in range(n_sub):
                tw.step(interval_seconds / n_sub)
            if tw.failures:
                tw.failures.clear()
                for c, i in _CI.items():
                    if tw.D[0, i] >= 1.0:
                        tw.repair(0, c)
            r = _package(tw, tw.read())
            r["time"] = t0 + timedelta(seconds=s * interval_seconds)
            rows.append(r)
    return pd.DataFrame(rows)


# ═════════════════════════════════════════════════════════════════════════
# 8) GELECEK PROJEKSİYONU — hasar modelini ileri sar
# ═════════════════════════════════════════════════════════════════════════
def project_future(equipment_id: str, hours: float) -> dict:
    """"Bu makine N saat daha (ortalama döngü stresiyle) çalışırsa?" Hasar
    denklemini analitik olarak ileri sarar; bir kopyada kısa fiziksel
    simülasyonla örnek sensör okuması üretir."""
    if equipment_id not in EQUIPMENT_PROFILES:
        return {"hata": f"Bilinmeyen ekipman: {equipment_id}"}
    tw = copy.deepcopy(get_twin(equipment_id))
    tw.rng = np.random.default_rng()
    h = float(hours)
    gs = tw.g[0] * tw.s_avg
    start = np.maximum(tw.op_hours[0], tw.onset[0])
    grow_h = np.clip(tw.op_hours[0] + h - start, 0, None)
    D_new = np.where(np.isfinite(tw.onset[0]),
                     np.minimum(1.0, (tw.D[0] + D_OFFSET) * np.exp(gs * grow_h) - D_OFFSET),
                     tw.D[0])
    D_new = np.maximum(D_new, tw.D[0])
    tw.D[0] = D_new
    tw.op_hours[0] += h
    tw.accel = 0.0
    for _ in range(300):
        tw.step(1.0)
    sample = _package(tw, tw.read())
    worst = int(np.argmax(D_new))
    w = float(D_new[worst])
    arizali = [COMPONENT_NAMES[i] for i in np.nonzero(D_new >= 1.0)[0]]
    return {
        "equipment_id": equipment_id,
        "saat_sonra": h,
        "projekte_calisma_saati": round(float(tw.op_hours[0]), 1),
        "projekte_yipranma": round(w, 3),
        "yipranma_yuzde": round(w * 100, 1),
        "bilesen_hasar": {c: round(float(D_new[i]), 3) for c, i in _CI.items()},
        "en_riskli_bilesen": COMPONENT_NAMES[worst],
        "arizalanacak_bilesenler": arizali,
        "ornek_sensor_okuma": sample,
        "not": "Projeksiyon yalnız şu an BAŞLAMIŞ hasarları ilerletir; henüz "
               "başlamamış (kuluçkadaki) arızalar öngörülemez.",
        "uyari": ("Projeksiyon süresi içinde arıza bekleniyor: " + ", ".join(arizali)) if arizali else
                 ("Hasar %50'yi aşıyor — erken bakım önerilir." if w > 0.5 else
                  "Yıpranma normal aralıkta — planlı bakım takvimi yeterli."),
    }
