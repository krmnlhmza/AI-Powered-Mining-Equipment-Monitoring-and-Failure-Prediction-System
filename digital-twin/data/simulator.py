"""
Dijital İkiz Simülatörü — Sandvik LH517i / TH551i için gerçekçi sensör üreteci
─────────────────────────────────────────────────────────────────────────────
Sahadaki bir makineyi sadece "rastgele dağılım + bazen spike" diye değil,
gerçek bir madencilik operasyon döngüsü olarak modelliyoruz.

3 ana mekanizma birleştirilmiştir:

  1) DURUM MAKİNESİ (state machine)
     Her makine kendi tipinin operasyon döngüsünde dolaşır:
       • LH517i (LHD yükleyici):  idle → yığına yaklaş → kepçe doldur →
                                  yüklü taşı → boşaltma noktası → boşalt →
                                  boş dön → (döngü başa)
       • TH551i (kamyon):         beklemede → yüklenme → yüklü hızlanma →
                                  yokuş yukarı yüklü → boşaltma yaklaşma →
                                  boşalt → yokuş aşağı boş → boş hızlanma

  2) SENSÖR KORELASYONLARI
     Sensörler birbirinden bağımsız değil. Yük artarsa sıcaklık + akım +
     titreşim birlikte artar; hidrolik aksiyonda (kepçe kaldırma, boşaltma)
     basınç spike yapar; yokuş aşağı = serin + hızlı + düşük tork.

  3) ZAMAN VE YIPRANMA
     Çalışma saatleri biriktikçe `wear_level` (0.0 → 1.0) artar; yıpranmış
     rulmanlar titreşim ve sıcaklık tabanını yukarı kaydırır. Yüksek stres
     (uzun ısı, uzun titreşim) yıpranmayı hızlandırır.

Geriye dönük uyumluluk: eski API çağrıları (generate_reading,
generate_training_data, generate_degradation_run, vb.) korunmuştur.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Tuple


# ═════════════════════════════════════════════════════════════════════════
# 1) EKİPMAN PROFİLLERİ — Sandvik teknik dokümantasyonu
# ═════════════════════════════════════════════════════════════════════════
EQUIPMENT_PROFILES: Dict[str, dict] = {
    # ── Sandvik LH517i — Yer Altı LHD Yükleyici (Volvo TAD1342VE, 354 kW)
    "LH517i_001": {
        "type":  "loader",
        "model": "Sandvik LH517i",
        "label": "LH517i #1 — Yükleyici",
        "temperature": (72, 88),    # °C — motor/hidrolik
        "vibration":   (0.8, 4.5),  # mm/s RMS
        "pressure":    (250, 280),  # bar — hidrolik
        "current":     (150, 195),  # A — sürücü motor
        "speed":       (1.0, 7.0),  # km/h
        "gas":         (0.1, 0.6),  # % CH4
        "rpm":         (800, 2100),   # devir — rölanti/max (Volvo TAD1342VE)
        "torque":      (300, 2300),   # Nm — tepe tork
        "fuel":        (8, 52),       # L/sa — rölanti/tam yük
    },
    "LH517i_002": {
        "type":  "loader",
        "model": "Sandvik LH517i",
        "label": "LH517i #2 — Yükleyici",
        "temperature": (72, 88),
        "vibration":   (0.8, 4.5),
        "pressure":    (250, 280),
        "current":     (150, 195),
        "speed":       (1.0, 7.0),
        "gas":         (0.1, 0.6),
        "rpm":         (800, 2100),
        "torque":      (300, 2300),
        "fuel":        (8, 52),
    },
    # ── Sandvik TH551i — Yer Altı Kamyon (411 kW, 51 ton kapasite)
    "TH551i_001": {
        "type":  "truck",
        "model": "Sandvik TH551i",
        "label": "TH551i #1 — Kamyon",
        "temperature": (75, 92),
        "vibration":   (1.0, 5.0),
        "pressure":    (200, 250),
        "current":     (180, 220),
        "speed":       (2.0, 30.0),
        "gas":         (0.1, 0.6),
        "rpm":         (800, 2100),
        "torque":      (400, 2600),   # 411 kW motor — daha yüksek tepe tork
        "fuel":        (10, 62),
    },
}


# ═════════════════════════════════════════════════════════════════════════
# 2) METAN (CH4) — İSG Güvenlik Eşikleri
# ═════════════════════════════════════════════════════════════════════════
METHANE_LIMITS = {
    "uyari":   1.0,   # %1.0 üzeri: uyarı, havalandırma kontrol
    "tehlike": 1.5,   # %1.5 üzeri: elektrikli ekipmanı durdur
    "kritik":  2.0,   # %2.0 üzeri: TAHLİYE (patlama aralığı %5-15)
}


def gas_status(gas_pct: float) -> dict:
    """Metan seviyesini İSG durumuna sınıflandırır."""
    if gas_pct >= METHANE_LIMITS["kritik"]:
        return {"seviye": "KRİTİK", "renk": "kirmizi",
                "mesaj": f"TAHLİYE — Metan %{gas_pct:.2f} (patlama riski). Tüm personel tahliye edilmeli."}
    if gas_pct >= METHANE_LIMITS["tehlike"]:
        return {"seviye": "TEHLİKE", "renk": "turuncu",
                "mesaj": f"Metan %{gas_pct:.2f} — Elektrikli ekipmanı durdurun, havalandırmayı artırın."}
    if gas_pct >= METHANE_LIMITS["uyari"]:
        return {"seviye": "UYARI", "renk": "sari",
                "mesaj": f"Metan %{gas_pct:.2f} — Eşik aşıldı, havalandırma kontrol edilmeli."}
    return {"seviye": "NORMAL", "renk": "yesil",
            "mesaj": f"Metan %{gas_pct:.2f} — Güvenli aralık."}


# ═════════════════════════════════════════════════════════════════════════
# 3) DURUM MAKİNESİ — Operasyon döngüsü
# ═════════════════════════════════════════════════════════════════════════
# Her faz: (faz adı, süresi saniye). Faz bittiğinde sıradakine geçilir,
# döngü sonunda başa döner. Saniye değerleri Sandvik OEM cycle time
# raporlarındaki tipik yer altı LHD/Kamyon değerleridir.
LHD_CYCLE: List[Tuple[str, int]] = [
    ("idle",              5),    # rölantide bekliyor
    ("approach_pile",     8),    # yığına yaklaşıyor
    ("picking_up",       10),    # kepçeyle dolduruyor — hidrolik spike
    ("hauling_loaded",   30),    # yüklü taşıyor — max stres
    ("approach_dump",    10),    # boşaltma noktasına yavaşlıyor
    ("dumping",           6),    # boşaltıyor — hidrolik spike
    ("returning_empty",  25),    # boş dönüyor — hafif yük
]

TRUCK_CYCLE: List[Tuple[str, int]] = [
    ("idle_waiting",       12),  # loader'ı bekliyor
    ("getting_loaded",     20),  # üzerine malzeme dökülüyor — titreşim
    ("accelerating_loaded",10),  # yüklü hızlanıyor — akım pik
    ("climbing_loaded",    45),  # yokuş yukarı yüklü — max her şey
    ("arriving_dump",      10),  # boşaltma noktasına yavaşlıyor
    ("dumping",             6),  # boşaltıyor
    ("descending_empty",   35),  # yokuş aşağı boş — rejeneratif fren, serin
    ("accelerating_empty",  8),  # boş hızlanıyor
]


def _cycle_for(eq_type: str) -> List[Tuple[str, int]]:
    return TRUCK_CYCLE if eq_type == "truck" else LHD_CYCLE


# Faz başına davranış parametreleri:
#   load          : 0.0 (boş) → 1.0 (tam yüklü)
#   throttle      : motor yükü, gaz pedalı seviyesi (0-1)
#   vibration_mult: titreşim çarpanı (1.0 = nominal)
#   speed_mult    : profil hız aralığında çarpan (0=dur, 1=max)
#   pressure_spike: True ise hidrolik basıncı geçici olarak max'ın üstüne
#   cooling       : True ise sıcaklık aktif düşer (rejeneratif/serbest)
PHASE_PROFILES: Dict[str, dict] = {
    # LHD fazları
    "idle":               {"load": 0.0, "throttle": 0.10, "vibration_mult": 0.4, "speed_mult": 0.0},
    "approach_pile":      {"load": 0.0, "throttle": 0.50, "vibration_mult": 0.7, "speed_mult": 0.7},
    "picking_up":         {"load": 0.7, "throttle": 0.90, "vibration_mult": 1.6, "speed_mult": 0.2, "pressure_spike": True},
    "hauling_loaded":     {"load": 1.0, "throttle": 0.85, "vibration_mult": 1.1, "speed_mult": 0.5},
    "approach_dump":      {"load": 1.0, "throttle": 0.30, "vibration_mult": 0.8, "speed_mult": 0.4},
    "dumping":            {"load": 0.4, "throttle": 0.60, "vibration_mult": 1.4, "speed_mult": 0.1, "pressure_spike": True},
    "returning_empty":    {"load": 0.0, "throttle": 0.65, "vibration_mult": 0.6, "speed_mult": 0.9},
    # Kamyon fazları
    "idle_waiting":       {"load": 0.0, "throttle": 0.10, "vibration_mult": 0.35, "speed_mult": 0.0},
    "getting_loaded":     {"load": 0.6, "throttle": 0.20, "vibration_mult": 1.5,  "speed_mult": 0.0},
    "accelerating_loaded":{"load": 1.0, "throttle": 1.00, "vibration_mult": 1.2,  "speed_mult": 0.4},
    "climbing_loaded":    {"load": 1.0, "throttle": 1.00, "vibration_mult": 1.0,  "speed_mult": 0.25},
    "arriving_dump":      {"load": 1.0, "throttle": 0.30, "vibration_mult": 0.7,  "speed_mult": 0.5},
    "descending_empty":   {"load": 0.0, "throttle": 0.30, "vibration_mult": 0.5,  "speed_mult": 0.85, "cooling": True},
    "accelerating_empty": {"load": 0.0, "throttle": 0.80, "vibration_mult": 0.7,  "speed_mult": 0.9},
    # (Senaryo 1) Manuel koşul — döngüde YOK: kötü/taşlık zeminde yüklü ilerleme.
    # Fizik: bozuk zemin → yüksek titreşim; araç zorlanır → yüksek gaz/devir/yakıt
    # ve sıcaklık; ama düşük hız. Bu bir NORMAL çalışma koşuludur (arıza değil),
    # bu yüzden IF eğitimine dahil edilir — aksi halde IF bunu anomali sanır.
    "kotu_yol":           {"load": 0.8, "throttle": 0.95, "vibration_mult": 1.9,  "speed_mult": 0.25},
}


# ═════════════════════════════════════════════════════════════════════════
# (Senaryo 1) MANUEL SEÇİLEBİLİR FİZİKSEL KOŞULLAR
# ─────────────────────────────────────────────────────────────────────────
# Kullanıcı Detay'dan bir koşul seçer; makine o koşulda SABİT kalır (döngü
# ilerlemez). Her koşul bir PHASE_PROFILES girdisine bağlanır. Liste araç
# TİPİNE göre değişir (yükleyici vs kamyon). "auto" = operasyon döngüsü.
# Bu tek kaynak hem UI hem de IF eğitimi tarafından kullanılır.
MANUAL_SCENARIOS: Dict[str, List[Tuple[str, str]]] = {
    "loader": [
        ("idle",            "Rölanti — bekleme"),
        ("returning_empty", "Boş — düz yol (hızlı)"),
        ("picking_up",      "Kepçe doldurma (hidrolik yük)"),
        ("hauling_loaded",  "Yüklü — taşıma"),
        ("kotu_yol",        "Kötü / taşlık yol — yüklü"),
    ],
    "truck": [
        ("idle_waiting",        "Rölanti — bekleme"),
        ("descending_empty",    "Boş — yokuş aşağı (serin, hızlı)"),
        ("accelerating_loaded", "Yüklü — düz yol"),
        ("climbing_loaded",     "Yüklü — yokuş yukarı (max stres)"),
        ("kotu_yol",            "Kötü / taşlık yol — yüklü"),
    ],
}


def manual_scenarios_for(eq_type: str) -> List[Tuple[str, str]]:
    """Araç tipine göre manuel seçilebilir fiziksel koşul listesi."""
    return MANUAL_SCENARIOS.get(eq_type, MANUAL_SCENARIOS["loader"])


@dataclass
class EquipmentRuntimeState:
    """Bir makinenin canlı durumu (uygulama belleğinde tutulur)."""
    cycle_phase:    str   = "idle"
    phase_elapsed:  float = 0.0      # bu fazda geçen saniye
    runtime_hours:  float = 0.0      # toplam çalışma saati
    wear_level:     float = 0.05     # 0.0 yeni → 1.0 arızalı
    last_update:    Optional[datetime] = None
    forced_fault:   Optional[str] = None    # enjekte edilen arıza tipi
    manual_phase:   Optional[str] = None    # (Senaryo 1) elle sabitlenen faz —
    # dolu ise döngü İLERLEMEZ, makine seçilen fiziksel koşulda kalır
    # (örn. "yokuş yukarı yüklü"). None = otomatik operasyon döngüsü.
    fault_readings_left: int = 0     # arızanın süreceği kalan okuma sayısı
    # (Adım 4) Arıza artık tek okumada kaybolmuyor: gerçekte bir rulman
    # bir saniyeliğine bozulup düzelmez. Enjeksiyon 4-6 okuma sürer;
    # böylece hem simülasyon gerçekçi olur hem de tespit güvenilirliği artar
    # (tek okumada ~%60-70 yakalanan arıza, 4-6 ardışık okumada ~%100).
    last_fault:    Optional[str] = None       # (Senaryo 2) son enjekte arıza tipi
    last_fault_ts: Optional[datetime] = None  # ve zamanı — RUL gömme penceresi için:
    # forced_fault sönse bile enjeksiyondan ~25 sn içinde RUL bu arızayı gösterir
    # (rulNotify ile forced_fault arasındaki zamanlama yarışını kapatır).


_states: Dict[str, EquipmentRuntimeState] = {}


def _get_state(equipment_id: str) -> EquipmentRuntimeState:
    if equipment_id not in _states:
        # Makineler "yepyeni" değil — bir miktar geçmiş çalışmayla başlasın
        # (demoda gerçekçilik için).
        _states[equipment_id] = EquipmentRuntimeState(
            wear_level    = float(np.random.uniform(0.05, 0.20)),
            runtime_hours = float(np.random.uniform(150, 800)),
            last_update   = datetime.now(timezone.utc),
        )
    return _states[equipment_id]


def _advance_state(state: EquipmentRuntimeState, eq_type: str,
                   dt_seconds: float) -> None:
    """Durum makinesini dt_seconds kadar ilerlet.
    Manuel mod: faz sabit kalır (döngü ilerlemez), yıpranma/saat yine birikir."""
    if state.manual_phase:
        state.cycle_phase = state.manual_phase
        state.runtime_hours += dt_seconds / 3600.0
        return
    cycle = _cycle_for(eq_type)
    phases    = [p[0] for p in cycle]
    durations = [p[1] for p in cycle]

    if state.cycle_phase not in phases:
        state.cycle_phase   = phases[0]
        state.phase_elapsed = 0.0

    state.phase_elapsed += dt_seconds
    idx = phases.index(state.cycle_phase)
    # Faz süresi dolduysa sıradakine geç
    while state.phase_elapsed >= durations[idx]:
        state.phase_elapsed -= durations[idx]
        idx = (idx + 1) % len(phases)
        state.cycle_phase = phases[idx]

    # Çalışma saatleri biriksin (faz "idle" olsa bile motor çalışıyor)
    state.runtime_hours += dt_seconds / 3600.0

    # Yıpranma modeli: madencilik LHD/Kamyon MTBF ~5000–8000 saat.
    # Baz yıpranma hızı: 5000 saatte %100 (yalnız stres çarpanı 1.0 iken).
    # Yüksek yük + titreşimli fazlar bunu 2–3x hızlandırabilir.
    phase_cfg = PHASE_PROFILES.get(state.cycle_phase, {})
    stress_mul = 1.0 + 1.0 * phase_cfg.get("load", 0.0) \
                     + 0.4 * (phase_cfg.get("vibration_mult", 1.0) - 1.0)
    base_rate  = 1.0 / (5000 * 3600)   # birim: 1/saniye → 5000 saat = %100
    state.wear_level = min(1.0,
        state.wear_level + base_rate * stress_mul * dt_seconds)


# ═════════════════════════════════════════════════════════════════════════
# 4) FİZİKSEL OKUMA HESABI — Korelasyonlu sensör değerleri
# ═════════════════════════════════════════════════════════════════════════
def _compute_reading(equipment_id: str, state: EquipmentRuntimeState) -> dict:
    """
    Durum + yıpranma + faz konfigürasyonundan tek bir sensör okuması üretir.
    Tüm sensörler birbirleriyle korelasyonlu (gerçek fizik).
    """
    profile   = EQUIPMENT_PROFILES[equipment_id]
    phase_cfg = PHASE_PROFILES.get(state.cycle_phase, PHASE_PROFILES["idle"])

    load     = phase_cfg.get("load", 0.0)
    throttle = phase_cfg.get("throttle", 0.5)
    vib_mul  = phase_cfg.get("vibration_mult", 1.0)
    spd_mul  = phase_cfg.get("speed_mult", 0.5)
    spike    = phase_cfg.get("pressure_spike", False)
    cooling  = phase_cfg.get("cooling", False)
    wear     = state.wear_level

    # ── Sıcaklık ──────────────────────────────────────────────
    # Taban + yük katkısı + yıpranma + soğutma (yokuş aşağı) + gürültü
    t_lo, t_hi = profile["temperature"]
    t_range = t_hi - t_lo
    t = t_lo + 0.5 * t_range                        # baz
    t += t_range * 0.7 * load                       # yük → ısı
    t += t_range * 0.5 * wear                       # yıpranma → ısı
    if cooling:
        t -= t_range * 0.4                          # yokuş aşağı → soğuk
    t += np.random.normal(0, t_range * 0.04)

    # ── Akım (motor) ──────────────────────────────────────────
    c_lo, c_hi = profile["current"]
    c_range = c_hi - c_lo
    c = c_lo + 0.2 * c_range                        # baz akım
    c += c_range * 0.9 * throttle                   # gaz → akım
    c += c_range * 0.4 * load                       # yük → ek akım
    c += np.random.normal(0, c_range * 0.05)

    # ── Titreşim ──────────────────────────────────────────────
    v_lo, v_hi = profile["vibration"]
    v_range = v_hi - v_lo
    # Titreşim motor aktivitesiyle orantılı: devir (≈throttle) arttıkça artar;
    # yük ve faz karakteri (kepçe/boşaltma/bozuk yol) ek katkı verir; yıpranma
    # tabanı yükseltir. Böylece devir–tork–titreşim birlikte hareket eder.
    v = v_lo + v_range * 0.15                       # rölanti motor titreşimi (taban)
    v += v_range * 0.30 * throttle                  # devir arttıkça titreşim
    v += v_range * 0.15 * load                      # yük → titreşim
    v += v_range * 0.30 * max(0.0, vib_mul - 1.0)   # faza özel ek (kepçe/boşaltma/bozuk yol)
    v += v_range * 0.45 * wear                      # yıpranmış rulman → titreşim
    v += np.random.normal(0, v_range * 0.06)
    v  = max(0.05, v)

    # ── Hidrolik basınç ───────────────────────────────────────
    p_lo, p_hi = profile["pressure"]
    p_range = p_hi - p_lo
    p = p_lo + 0.5 * p_range                        # nominal orta
    if spike:                                       # kepçe/boşaltma anı
        p = p_hi + p_range * 0.1
    p += np.random.normal(0, p_range * 0.03)

    # ── Hız ───────────────────────────────────────────────────
    s_lo, s_hi = profile["speed"]
    s_range = s_hi - s_lo
    if spd_mul <= 0.0:
        s = 0.0                       # durağan faz (rölanti/yüklenme) → hız tam 0
    else:
        s = s_lo + spd_mul * s_range + np.random.normal(0, s_range * 0.05)
        s = max(0.0, s)

    # ── Devir / Tork / Yakıt (güç aktarma — fizik korelasyonlu) ──
    # Devir gaz pedalını izler; tork yük+gazla; yakıt devir+yük+yıpranmayla
    # birlikte artar. Yokuş senaryosunda: hız düşer, tork/devir/yakıt yükselir.
    r_lo, r_hi = profile["rpm"]
    rpm = r_lo + (r_hi - r_lo) * throttle + np.random.normal(0, (r_hi - r_lo) * 0.03)
    tq_lo, tq_hi = profile["torque"]
    tork = tq_lo + (tq_hi - tq_lo) * min(1.0, 0.55 * load + 0.45 * throttle) \
           + np.random.normal(0, (tq_hi - tq_lo) * 0.03)
    if cooling:
        tork *= 0.35          # yokuş aşağı: motor freni, tork düşük

    # ── Rölanti (durağan + yüksüz): motor sabit rölanti devrinde döner, araç
    # durur, tahrik torku ~0'dır. Değerler ekranda titremesin diye çok az
    # gürültüyle neredeyse sabit tutulur.
    if spd_mul <= 0.0 and load <= 0.0 and throttle <= 0.15:
        rpm  = r_lo + np.random.normal(0, (r_hi - r_lo) * 0.004)   # sabit rölanti devri
        tork = max(0.0, tq_lo * 0.03 + np.random.normal(0, tq_lo * 0.004))  # ~sabit, ~0
    f_lo, f_hi = profile["fuel"]
    yakit = f_lo + (f_hi - f_lo) * min(1.0, 0.55 * throttle + 0.35 * load + 0.15 * wear) \
            + np.random.normal(0, (f_hi - f_lo) * 0.04)

    # ── Metan (ortam) ─────────────────────────────────────────
    # Mekanikten bağımsız, ortam fonu. force_gas dışarıdan setlenir.
    g_lo, g_hi = profile["gas"]
    g = max(0.0, np.random.normal((g_lo + g_hi) / 2, (g_hi - g_lo) / 4))

    # ── Zorlanan arıza enjeksiyonu (yalnız Canlı Test'ten gelir) ──
    # Arıza şiddeti MUTLAKTIR: gerçek bir rulman arızası "rölantinin 2 katı"
    # değil, kritik eşiğe vurmuş mutlak yüksek titreşim üretir. Çarpan yerine
    # "kritik eşiğin %90-110'u" tabanı kullanılır — makine hangi fazda olursa
    # olsun arıza belirgin görünür ve 2/3 teyit kuralından güvenilirce geçer.
    if state.forced_fault:
        _crit = {k: profile[k][1] * m for k, m in
                 (("temperature", 1.45), ("vibration", 2.8),
                  ("current", 1.6), ("pressure", 1.7))}
        hi_t = profile["temperature"][1]
        ff = state.forced_fault
        # ── (Senaryo 2) Çok-sensörlü, gerçekçi arıza imzaları ──
        # Her imza IF'in gördüğü 5 sensörden (sıcaklık, titreşim, basınç, akım,
        # hız) en az birinde belirgin sapar → tespit garanti. Yakıt/tork/devir
        # de fizik gereği birlikte hareket eder (arayüzde görünür).
        if ff in ("yag_pompasi", "pump"):
            # Yağ/hidrolik pompa arızası: pompa basıncı tutamaz → BASINÇ DÜŞER;
            # yağ dolaşımı azalır → yağ ısısı hafif düşer; mekanik zorlanma →
            # titreşim artar; motor telafi için daha çok yakar.
            p = min(p, p_lo * np.random.uniform(0.42, 0.55))
            v = max(v, _crit["vibration"] * np.random.uniform(0.72, 0.92))
            t = t - t_range * np.random.uniform(0.15, 0.30)
            yakit *= np.random.uniform(1.12, 1.22)
        elif ff in ("rulman", "vibration_spike"):
            # Rulman aşınması: sürtünme → yüksek titreşim + ısı hafif yükselir.
            v = max(v, _crit["vibration"] * np.random.uniform(0.95, 1.15))
            t = max(t, hi_t * np.random.uniform(1.02, 1.08))
        elif ff == "overheat":
            # Motor aşırı ısınma: ısı kritik + ısınan motor daha çok akım çeker.
            t = max(t, _crit["temperature"] * np.random.uniform(0.95, 1.10))
            c = max(c, profile["current"][1] * np.random.uniform(1.05, 1.20))
        elif ff in ("enjektor", "injector"):
            # Enjektör/yanma arızası: düzensiz yanma (misfire) → titreşim artar,
            # tork düşer, motor telafi için daha çok yakar, egzoz ısısı hafif artar.
            v = max(v, _crit["vibration"] * np.random.uniform(0.70, 0.90))
            yakit *= np.random.uniform(1.20, 1.35)
            tork *= np.random.uniform(0.60, 0.75)
            t = max(t, hi_t * np.random.uniform(1.02, 1.06))
        elif ff == "fren":
            # Fren aşırı ısınması: sürtünme ısısı → sıcaklık yükselir; balata
            # sürtmesi → titreşim ve düşük/düzensiz hız (fren dragı).
            t = max(t, _crit["temperature"] * np.random.uniform(0.80, 0.92))
            v = max(v, _crit["vibration"] * np.random.uniform(0.55, 0.75))
            s = s * np.random.uniform(0.25, 0.45)
        elif ff in ("transmisyon", "sanziman"):
            # Transmisyon/güç aktarma arızası: dişli/rulman hasarı → yüksek
            # titreşim + şanzıman yağ sıcaklığı yükselir.
            v = max(v, _crit["vibration"] * np.random.uniform(0.75, 0.95))
            t = max(t, hi_t * np.random.uniform(1.06, 1.14))
        elif ff in ("sogutma", "cooling"):
            # Soğutma sistemi arızası (radyatör/fan): soğutma verimi düşer →
            # sıcaklık sürekli yükselir (akım normal — motorun kendisi değil).
            t = max(t, _crit["temperature"] * np.random.uniform(0.88, 1.02))
        elif ff == "overcurrent":
            # Aşırı akım / motor sargı zorlanması: akım sürekli üst sınırın
            # üstünde + sargı ısınması.
            c = max(c, _crit["current"] * np.random.uniform(0.90, 1.08))
            t = max(t, hi_t * np.random.uniform(1.03, 1.10))
        elif ff == "pressure_surge":
            p = max(p, _crit["pressure"] * np.random.uniform(0.92, 1.08))
    if state.forced_fault:
        state.fault_readings_left -= 1
        if state.fault_readings_left <= 0:
            state.forced_fault = None   # arıza süresi doldu

    return {
        "temperature": round(float(t), 3),
        "vibration":   round(float(v), 3),
        "pressure":    round(float(p), 3),
        "current":     round(float(c), 3),
        "speed":       round(float(s), 3),
        "gas":         round(float(g), 3),
        "rpm":         round(float(max(0, rpm)), 1),
        "torque":      round(float(max(0, tork)), 1),
        "fuel":        round(float(max(0, yakit)), 2),
    }


# ═════════════════════════════════════════════════════════════════════════
# 5) DIŞA AÇIK API — Geriye dönük uyumlu fonksiyonlar
# ═════════════════════════════════════════════════════════════════════════
def set_manual_phase(equipment_id: str, phase) -> None:
    """(Senaryo 1) Aracın fiziksel koşulunu elle sabitle; None/'auto' = döngüye dön."""
    st = _get_state(equipment_id)
    st.manual_phase = None if phase in (None, "auto") else phase


def generate_reading(equipment_id: str, force_anomaly: bool = False,
                     force_gas: bool = False, fault_type: str = None) -> dict:
    """
    Canlı stream için: durum makinesini bir adım ilerletip korelasyonlu
    sensör okuması döner. force_anomaly=True ise sonraki okumaya rastgele
    bir arıza enjekte edilir; force_gas=True ise metan anlık olarak
    İSG eşiklerinin üzerine çıkar.
    """
    if equipment_id not in EQUIPMENT_PROFILES:
        equipment_id = next(iter(EQUIPMENT_PROFILES))

    profile = EQUIPMENT_PROFILES[equipment_id]
    state   = _get_state(equipment_id)

    # Gerçek geçen süreyi ölç (uvicorn akışında ~8 sn, manuel testte değişebilir)
    now = datetime.now(timezone.utc)
    if state.last_update is None:
        dt = 8.0
    else:
        dt = (now - state.last_update).total_seconds()
        dt = max(0.5, min(dt, 30.0))   # 0.5–30 sn arası clamp (zıplama önlemi)
    state.last_update = now

    _advance_state(state, profile["type"], dt)

    if force_anomaly:
        # (Senaryo 2) fault_type verilirse O arıza enjekte edilir; yoksa rastgele
        state.forced_fault = fault_type or np.random.choice(
            ["yag_pompasi", "rulman", "overheat", "enjektor",
             "overcurrent", "fren", "transmisyon", "sogutma"]
        )
        state.last_fault = state.forced_fault
        state.last_fault_ts = datetime.now(timezone.utc)
        # Kısa tek olay: enjekte arıza garanti tespit edildiğinden bu pencere
        # ≈ grafikteki anomali nokta sayısıdır. 4 okuma ≈ kısa bir spike; arıza
        # bitince anomali hemen temizlenir. Alarm kenar-tetikli olduğundan tek düşer.
        state.fault_readings_left = int(np.random.randint(3, 5))

    reading = _compute_reading(equipment_id, state)

    if force_gas:
        reading["gas"] = round(float(np.random.uniform(1.2, 2.6)), 3)

    reading["equipment_id"]   = equipment_id
    reading["equipment_type"] = profile["type"]
    reading["phase"]          = state.cycle_phase
    reading["wear_level"]     = round(state.wear_level, 4)
    reading["runtime_hours"]  = round(state.runtime_hours, 1)
    return reading


# ─── Toplu/eğitim verileri ────────────────────────────────────────────
def _stateless_reading_for_phase(equipment_id: str, phase: str,
                                  wear: float = 0.1) -> dict:
    """Durum makinesine dokunmadan, belirli bir faz + yıpranma için
    tek seferlik okuma — eğitim verisi üretimi için."""
    tmp_state = EquipmentRuntimeState(cycle_phase=phase, wear_level=wear)
    return _compute_reading(equipment_id, tmp_state)


def _anomaly_reading(equipment_id: str) -> dict:
    """Tek bir sensörü kesin olarak spike eden anomali okuması (IF eğitimi
    için 'class 1' örnek)."""
    base = _stateless_reading_for_phase(
        equipment_id,
        phase=np.random.choice(list(PHASE_PROFILES.keys())),
        wear=float(np.random.uniform(0.1, 0.4)),
    )
    fault = np.random.choice(["overheat", "vibration_spike",
                              "overcurrent", "pressure_surge"])
    if fault == "overheat":
        base["temperature"] *= np.random.uniform(1.3, 1.55)
    elif fault == "vibration_spike":
        base["vibration"]   *= np.random.uniform(2.0, 3.0)
    elif fault == "overcurrent":
        base["current"]     *= np.random.uniform(1.4, 1.7)
    elif fault == "pressure_surge":
        base["pressure"]    *= np.random.uniform(1.4, 1.8)
    return base


def generate_training_data(n_samples: int = 2000) -> pd.DataFrame:
    """
    IF eğitimi için stateless örnekleme: tüm operasyon fazlarını ve
    yıpranma seviyelerini uniform tarayıp ~%5 anomali enjekte eder.
    """
    rows = []
    eq_ids = list(EQUIPMENT_PROFILES.keys())
    phases = list(PHASE_PROFILES.keys())

    for _ in range(n_samples):
        eq_id = np.random.choice(eq_ids)
        # Sadece o ekipmanın tipine uygun fazlardan seç
        eq_type = EQUIPMENT_PROFILES[eq_id]["type"]
        # Döngü fazları + manuel seçilebilir koşullar (kotu_yol dahil) — hepsi
        # NORMAL çalışma sayılır, IF bunları anomali olarak işaretlememeli.
        valid_phases = list(dict.fromkeys(
            [p for p, _ in _cycle_for(eq_type)]
            + [p for p, _ in manual_scenarios_for(eq_type)]
        ))
        # "Hafif" fazlar (rölanti, boş dönüş, yokuş aşağı boş inme) normal
        # uzayın uç köşeleridir: hız/yük düşük, soğumada sıcaklık da düşer.
        # Eşit örneklenirse seyrek kalır ve IF onları yanlışlıkla anomali sanar
        # (idle %20, iniş %25 sahte alarm). Gerçek operasyonda makine bu
        # durumlarda çok zaman geçirir → eğitimde bol olmalı. 3x ağırlık:
        # IF bu köşeleri yoğun/normal öğrenir, sahte alarm hedefi <%2.
        # Ayrıca "dumping" hidrolik basıncı ani spike yapan geçici bir köşedir;
        # o da seyrek kalırsa sahte alarm üretir → aynı gerekçeyle yoğunlaştırılır.
        BOOST = ("idle", "idle_waiting", "returning_empty",
                 "descending_empty", "accelerating_empty", "dumping")
        w = np.array([3.0 if p in BOOST else 1.0 for p in valid_phases])
        phase = np.random.choice(valid_phases, p=w / w.sum())
        wear  = float(np.random.uniform(0.05, 0.5))
        is_anomaly = np.random.random() < 0.05
        if is_anomaly:
            reading = _anomaly_reading(eq_id)
        else:
            reading = _stateless_reading_for_phase(eq_id, phase, wear)
        reading["equipment_id"]   = eq_id
        reading["equipment_type"] = eq_type
        reading["phase"]          = phase
        reading["wear_level"]     = round(wear, 4)
        reading["is_anomaly"]     = is_anomaly
        rows.append(reading)
    return pd.DataFrame(rows)


def generate_historical(hours: int = 24, interval_seconds: int = 30) -> pd.DataFrame:
    """24 saatlik canlı stream taklidi — durum makinesini gerçek zamanda
    fast-forward eder, hypertable seed için kullanılır."""
    rows = []
    now = datetime.now(timezone.utc)
    t   = now - timedelta(hours=hours)
    # Geçici state'ler kullan (asıl runtime state'lere dokunma)
    temp_states: Dict[str, EquipmentRuntimeState] = {
        eq: EquipmentRuntimeState(
            wear_level    = float(np.random.uniform(0.05, 0.20)),
            runtime_hours = float(np.random.uniform(150, 800)),
            last_update   = t,
        )
        for eq in EQUIPMENT_PROFILES
    }
    while t <= now:
        for eq_id, st in temp_states.items():
            _advance_state(st, EQUIPMENT_PROFILES[eq_id]["type"],
                           dt_seconds=interval_seconds)
            r = _compute_reading(eq_id, st)
            r["equipment_id"]   = eq_id
            r["equipment_type"] = EQUIPMENT_PROFILES[eq_id]["type"]
            r["time"]           = t
            rows.append(r)
        t += timedelta(seconds=interval_seconds)
    return pd.DataFrame(rows)


# ═════════════════════════════════════════════════════════════════════════
# 6) RUL — Kalan Faydalı Ömür Eğitim Verisi (run-to-failure)
# ═════════════════════════════════════════════════════════════════════════
# Kritik eşik çarpanları (normal üst sınırın katı):
# Sensör bu eşiğe ulaşınca makine "arızalı" sayılır.
CRITICAL_MULTIPLIERS = {
    "temperature": 1.45,
    "vibration":   2.8,
    "current":     1.6,
    "pressure":    1.7,
}

DEGRADATION_MODES = {
    "rulman_asinmasi": {"primary": "vibration",   "secondary": "temperature", "sec_factor": 0.45},
    "asiri_isinma":    {"primary": "temperature", "secondary": "current",     "sec_factor": 0.40},
    "asiri_akim":      {"primary": "current",     "secondary": "temperature", "sec_factor": 0.35},
    "basinc_kaybi":    {"primary": "pressure",    "secondary": None,          "sec_factor": 0.0},
}

STEP_HOURS = 0.5   # her run-to-failure adımı 30 dakikalık ufuk


def critical_thresholds(equipment_id: str) -> dict:
    """Ekipmanın her sensörü için arıza (kritik) eşiği."""
    profile = EQUIPMENT_PROFILES[equipment_id]
    return {
        key: round(profile[key][1] * mult, 2)
        for key, mult in CRITICAL_MULTIPLIERS.items()
    }


def generate_degradation_run(equipment_id: str, steps: int = None,
                              mode: str = None) -> pd.DataFrame:
    """
    Tek bir 'sağlıklı → arıza' run-to-failure trajektorisi üretir.
    Bir sensör normal seviyeden kritik eşiğe doğru üstel hızlanan bir
    eğride kayar. RUL LSTM bu run'larla eğitilir.
    """
    profile = EQUIPMENT_PROFILES[equipment_id]
    if steps is None: steps = int(np.random.randint(80, 200))
    if mode  is None: mode  = np.random.choice(list(DEGRADATION_MODES.keys()))
    spec = DEGRADATION_MODES[mode]
    crit = critical_thresholds(equipment_id)

    rows = []
    for i in range(steps):
        progress = i / max(1, steps - 1)                  # 0 → 1
        sev      = progress ** 1.7                         # üstel hızlanma

        # Sağlıklı taban okumayı durum makinesine bağlı olmayan basit
        # rastgele örnek olarak al (rastgele bir fazdan):
        base = _stateless_reading_for_phase(
            equipment_id,
            phase=np.random.choice([p for p, _ in _cycle_for(profile["type"])]),
            wear=0.1 + progress * 0.5,
        )

        prim = spec["primary"]
        if prim == "pressure":
            lo = profile["pressure"][0]
            target_low = lo * 0.45
            base["pressure"] = float(
                lo - (lo - target_low) * sev
                + np.random.normal(0, 0.08)
            )
        else:
            hi = profile[prim][1]
            base[prim] = float(
                hi + (crit[prim] - hi) * sev
                + np.random.normal(0, (crit[prim] - hi) * 0.04)
            )

        sec = spec["secondary"]
        if sec:
            hi_s = profile[sec][1]
            base[sec] = float(
                base[sec] + (crit[sec] - hi_s) * sev * spec["sec_factor"]
            )

        base["equipment_id"]   = equipment_id
        base["equipment_type"] = profile["type"]
        base["mode"]           = mode
        base["health"]         = round(max(0.0, 1.0 - progress), 4)
        base["rul_hours"]      = round((steps - 1 - i) * STEP_HOURS, 3)
        rows.append(base)

    return pd.DataFrame(rows)


def generate_healthy_run(equipment_id: str, steps: int = None) -> pd.DataFrame:
    """Sağlıklı run — tüm pencereler max RUL ile etiketlenir."""
    profile = EQUIPMENT_PROFILES[equipment_id]
    if steps is None: steps = int(np.random.randint(40, 80))
    # Sağlıklı taban: döngü fazları + manuel koşullar (kotu_yol dahil) → RUL
    # modeli bu koşulları da "sağlıklı" normalde görsün.
    valid_phases = list(dict.fromkeys(
        [p for p, _ in _cycle_for(profile["type"])]
        + [p for p, _ in manual_scenarios_for(profile["type"])]
    ))
    rows = []
    for _ in range(steps):
        r = _stateless_reading_for_phase(
            equipment_id,
            phase=np.random.choice(valid_phases),
            wear=float(np.random.uniform(0.05, 0.25)),
        )
        r["equipment_id"]   = equipment_id
        r["equipment_type"] = profile["type"]
        r["mode"]           = "saglikli"
        r["health"]         = 1.0
        r["rul_hours"]      = float(STEP_HOURS * 200)
        rows.append(r)
    return pd.DataFrame(rows)


def generate_rul_dataset(runs_per_equipment: int = 40) -> pd.DataFrame:
    """RUL eğitim seti: her ekipman için degradasyon + sağlıklı run'lar."""
    frames = []
    rid = 0
    for eq_id in EQUIPMENT_PROFILES:
        for _ in range(runs_per_equipment):
            df = generate_degradation_run(eq_id)
            df["run_id"] = rid; rid += 1
            frames.append(df)
        for _ in range(runs_per_equipment // 2):
            df = generate_healthy_run(eq_id)
            df["run_id"] = rid; rid += 1
            frames.append(df)
    return pd.concat(frames, ignore_index=True)


# ═════════════════════════════════════════════════════════════════════════
# 7) GELECEKTEKİ DURUM PROJEKSİYONU (jüri demosu)
# ═════════════════════════════════════════════════════════════════════════
def project_future(equipment_id: str, hours: float) -> dict:
    """
    "Bu makine şu an gibi N saat daha çalışırsa ne durumda olur?" sorusunun
    cevabı. Mevcut durumun bir kopyası üzerinde durum makinesini
    fast-forward eder, projeksiyon değerleri döner.
    """
    if equipment_id not in EQUIPMENT_PROFILES:
        return {"hata": f"Bilinmeyen ekipman: {equipment_id}"}

    current = _get_state(equipment_id)
    # Kopya — gerçek state'e dokunmayalım
    sim = EquipmentRuntimeState(
        cycle_phase   = current.cycle_phase,
        phase_elapsed = current.phase_elapsed,
        runtime_hours = current.runtime_hours,
        wear_level    = current.wear_level,
        last_update   = current.last_update,
    )
    eq_type = EQUIPMENT_PROFILES[equipment_id]["type"]
    # 60 saniye adımlarla fast-forward (hız/doğruluk dengesi)
    seconds_left = hours * 3600.0
    step = 60.0
    while seconds_left > 0:
        _advance_state(sim, eq_type, min(step, seconds_left))
        seconds_left -= step
    sample = _compute_reading(equipment_id, sim)
    return {
        "equipment_id":           equipment_id,
        "saat_sonra":             hours,
        "projekte_calisma_saati": round(sim.runtime_hours, 1),
        "projekte_yipranma":      round(sim.wear_level, 3),
        "yipranma_yuzde":         round(sim.wear_level * 100, 1),
        "ornek_sensor_okuma":     sample,
        "uyari": "Yıpranma %50'yi aşarsa erken bakım önerilir; %80 üzeri kritik."
                 if sim.wear_level > 0.5 else
                 "Yıpranma normal aralıkta — planlı bakım takvimi yeterli.",
    }
