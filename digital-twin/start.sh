#!/bin/bash
# ─────────────────────────────────────────────────────────────
# Backend başlatma betiği (Adım 8/9)
# Neden var? İki taşınma kazasını kökten çözer:
#   1) Klasör taşınsa bile her zaman KENDİ bulunduğu yerden çalışır
#      (cd $(dirname $0)) → ml/, static/, fonts/, .env yolları hep doğru.
#   2) venv'i "python -m uvicorn" ile dolaylı çağırır → venv içindeki
#      ezberlenmiş eski yollar (shebang) hiç kullanılmaz.
# Kullanım:  ./start.sh          (ön koşul: docker compose up -d)
# ─────────────────────────────────────────────────────────────
cd "$(dirname "$0")" || exit 1

# venv yoksa kur (arkadaşın Mac'inde ilk kurulum için)
if [ ! -f ".venv/bin/python" ]; then
    echo "venv bulunamadı — kuruluyor (birkaç dakika sürebilir)..."
    python3 -m venv .venv
    .venv/bin/python -m pip install -q -r requirements.txt
fi

exec .venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
