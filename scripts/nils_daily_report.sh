#!/usr/bin/env bash
# Täglicher Nils-Report (Telegram + Mail)
# Secrets liest Python selbst (kein bash-source von Passwörtern).
set -euo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin"
cd /root/app
VENV_PY="/root/app/venv/bin/python"
if [ ! -x "$VENV_PY" ]; then
  VENV_PY="python3"
fi
export PYTHONPATH="/root/app/backend${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p /var/lib/webschmiede
exec "$VENV_PY" /root/app/scripts/nils_daily_report_cli.py >> /var/log/nils-daily-report.log 2>&1
