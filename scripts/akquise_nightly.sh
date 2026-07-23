#!/bin/bash
# Nightly Akquise auf auto-01
# Aufruf: akquise_nightly.sh [vertical]
# Ohne Argument: Rotation nach Wochentag (alle Branchen abdecken)
set -euo pipefail
cd /root/app
LOG=/var/log/akquise.log
SECRETS=/root/app/deploy.secrets.local

if [[ -f "$SECRETS" ]]; then
  KEY=$(grep -E '^GOOGLE_PLACES_API_KEY=' "$SECRETS" | head -1 | cut -d= -f2- | tr -d '\r' || true)
  export GOOGLE_PLACES_API_KEY="${KEY:-}"
  ND=$(grep -E '^NORTHDATA_API_KEY=' "$SECRETS" | head -1 | cut -d= -f2- | tr -d '\r' || true)
  if [[ -n "${ND:-}" ]]; then
    export NORTHDATA_API_KEY="$ND"
  fi
fi

# Mo–So Rotation: Gastro + Bau-Gewerke + Elektro
DOW=$(date +%u)  # 1=Mo … 7=So
WEEK=$(date +%V)
case "$DOW" in
  1) DEFAULT=gastro ;;
  2) DEFAULT=fliesenleger ;;
  3) DEFAULT=dach ;;
  4) DEFAULT=trockenbau ;;
  5) DEFAULT=elektro ;;
  6) DEFAULT=gartenbau ;;
  7)
    # So: Hochbau / Tiefbau im Wechsel
    if (( WEEK % 2 == 0 )); then DEFAULT=hochbau; else DEFAULT=tiefbau; fi
    ;;
  *) DEFAULT=gastro ;;
esac

VERTICAL="${1:-$DEFAULT}"
echo "===== $(date -Iseconds) vertical=$VERTICAL places=${#GOOGLE_PLACES_API_KEY} =====" >> "$LOG"
/usr/bin/python3 scripts/akquise_run.py --vertical "$VERTICAL" --workers 2 >> "$LOG" 2>&1 || {
  echo "===== $(date -Iseconds) FAIL $VERTICAL =====" >> "$LOG"
  exit 1
}

latest=$(ls -t docs/akquise/reports/*-"$VERTICAL".html 2>/dev/null | head -1 || true)
if [[ -n "${latest:-}" ]]; then
  mkdir -p /var/www/snackhouse-mechernich 2>/dev/null || true
  cp "$latest" /var/www/snackhouse-mechernich/akquise-report.html 2>/dev/null || true
  # Kopie auch lokal für Deploy-Sync
  cp "$latest" app/static/akquise-report.html 2>/dev/null || true
fi

# Optional: Lokal-News Radar (wenn Skript da)
if [[ -f scripts/akquise_local_news.py ]]; then
  /usr/bin/python3 scripts/akquise_local_news.py >> "$LOG" 2>&1 || true
fi

# Reverse-Akquise: Betriebe die Hilfe suchen
if [[ -f scripts/akquise_demand_scan.py ]]; then
  /usr/bin/python3 scripts/akquise_demand_scan.py >> "$LOG" 2>&1 || true
fi

# Jobs / Insolvenz / Neueröffnung
if [[ -f scripts/akquise_market_signals.py ]]; then
  /usr/bin/python3 scripts/akquise_market_signals.py >> "$LOG" 2>&1 || true
fi

echo "===== $(date -Iseconds) done $VERTICAL =====" >> "$LOG"
