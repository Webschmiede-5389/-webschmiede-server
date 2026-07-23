#!/usr/bin/env bash
set -euo pipefail
export TZ=Europe/Berlin
export PYTHONPATH=/root/app/backend:/root/app
cd /root/app
/usr/bin/python3 /root/app/scripts/route_watchdog.py >> /var/log/route-watchdog.log 2>&1
