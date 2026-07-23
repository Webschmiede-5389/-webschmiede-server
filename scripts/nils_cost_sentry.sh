#!/usr/bin/env bash
# Kosten-Wächter
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
exec "$VENV_PY" -c "import nils_cost_sentry as c; r=c.run(apply=True, notify=True); print(r.get('text',''))" >> /var/log/nils-cost-sentry.log 2>&1
