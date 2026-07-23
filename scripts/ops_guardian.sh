#!/usr/bin/env bash
# Ops-Guardian Cron-Wrapper (web-01)
set -euo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin"
cd /root/app
# Secrets + .env
set -a
[ -f /root/app/deploy.secrets.local ] && . /root/app/deploy.secrets.local
[ -f /root/app/backend/.env ] && . /root/app/backend/.env
set +a
VENV_PY="/root/app/venv/bin/python"
if [ ! -x "$VENV_PY" ]; then
  VENV_PY="python3"
fi
export PYTHONPATH="/root/app/backend${PYTHONPATH:+:$PYTHONPATH}"
exec "$VENV_PY" /root/app/scripts/ops_guardian_cli.py run --mail >> /var/log/ops-guardian.log 2>&1
