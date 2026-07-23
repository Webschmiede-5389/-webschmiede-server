#!/usr/bin/env bash
# Sales-Companion: Reminders + Tagesstand (web-01)
set -euo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin"
cd /root/app
set -a
[ -f /root/app/deploy.secrets.local ] && . /root/app/deploy.secrets.local
[ -f /root/app/backend/.env ] && . /root/app/backend/.env
set +a
SECRET="${CRON_SECRET:-}"
if [ -z "$SECRET" ]; then
  echo "CRON_SECRET fehlt" >> /var/log/sales-companion.log
  exit 1
fi
curl -sS -X POST "http://127.0.0.1:8000/api/cron/sales-companion" \
  -H "Content-Type: application/json" \
  -H "X-Cron-Secret: $SECRET" \
  -d '{"digest":1}' >> /var/log/sales-companion.log 2>&1
echo "" >> /var/log/sales-companion.log
