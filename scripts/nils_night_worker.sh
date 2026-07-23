#!/usr/bin/env bash
# Nils Night-Worker: Hirn-Wächter + Job-Watchdog + kurzer Digest
set -euo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin"
cd /root/app
VENV_PY="/root/app/venv/bin/python"
if [ ! -x "$VENV_PY" ]; then
  VENV_PY="python3"
fi
export PYTHONPATH="/root/app/backend${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p /var/lib/webschmiede
EXTRA=()
if [ "${1:-}" = "--night" ]; then
  EXTRA+=(--night)
fi
exec "$VENV_PY" /root/app/scripts/nils_night_worker_cli.py "${EXTRA[@]}" >> /var/log/nils-night-worker.log 2>&1
