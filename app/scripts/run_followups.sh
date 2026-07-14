#!/bin/bash
# Taeglich via cron ausfuehren: 0 10 * * * /root/app/scripts/run_followups.sh
set -e
source /root/app/backend/.env 2>/dev/null || true
SECRET="${CRON_SECRET:-}"
if [ -z "$SECRET" ]; then
  echo "CRON_SECRET not set"
  exit 1
fi
curl -sf -X POST "http://127.0.0.1:8000/api/cron/followups" \
  -H "X-Cron-Secret: $SECRET" \
  -H "Content-Type: application/json"
echo ""
