#!/bin/bash
# Kunden-Portale alle 15 Min
set -euo pipefail
export TZ=Europe/Berlin
export PYTHONPATH=/root/app/backend:/root/app
cd /root/app
/usr/bin/python3 /root/app/scripts/customer_portal_watchdog.py >> /var/log/customer-portal-watchdog.log 2>&1
