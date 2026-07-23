#!/bin/bash
# Taeglich nach den Nacht-Jobs: pruefen, reparieren, E-Mail
set -euo pipefail
cd /root/app/backend
/usr/bin/python3 nightly_watchdog.py --repair >> /var/log/nightly-watchdog.log 2>&1
