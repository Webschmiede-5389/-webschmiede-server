#!/bin/bash
# Cron-Wrapper: Hetzner Capacity Buyer
set -euo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
cd /root/app
LOG=/var/log/hetzner-buyer.log
mkdir -p /var/lib/webschmiede
{
  echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  /usr/bin/python3 /root/app/scripts/hetzner_capacity_buyer.py --force-try
  echo "exit=$?"
} >>"$LOG" 2>&1
