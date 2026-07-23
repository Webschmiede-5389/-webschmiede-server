#!/bin/bash
# Alle 15 Min: RAM/Disk/CPU prüfen, bei Grenzwert Mail
set -euo pipefail
cd /root/app/backend
/usr/bin/python3 resource_watchdog.py >> /var/log/resource-watchdog.log 2>&1
