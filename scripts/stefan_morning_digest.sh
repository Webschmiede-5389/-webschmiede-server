#!/usr/bin/env bash
# Stefan Morgen-Digest (Cron auf auto-01neu)
set -euo pipefail
export TZ=Europe/Berlin
export PYTHONPATH=/root/app/backend:/root/app
cd /root/app
/usr/bin/python3 /root/app/scripts/stefan_morning_digest.py >> /var/log/stefan-digest.log 2>&1
