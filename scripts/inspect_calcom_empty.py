#!/usr/bin/env python3
import os
import sys

import paramiko

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency_config import ssh_connect

cmd = r"""
echo '=== compose ==='
ls -la /opt/calcom/ 2>/dev/null | head -20
echo '=== env sample ==='
grep -E '^(NEXTAUTH_URL|NEXT_PUBLIC_WEBAPP_URL|WEBAPP_URL|DATABASE_URL|CALCOM_LICENSE)=' /opt/calcom/.env 2>/dev/null | sed 's/=.*/=***/'
echo '=== counts ==='
docker exec calcom-database-1 psql -U cal -d calendso -c 'SELECT (SELECT count(*) FROM users) AS users, (SELECT count(*) FROM "UserPassword") AS pw, (SELECT count(*) FROM "ApiKey") AS keys, (SELECT count(*) FROM "EventType") AS ets, (SELECT count(*) FROM "Schedule") AS schedules;'
echo '=== curl home ==='
curl -sI https://cal.digitalehandwerkskunst.de/ | head -12
echo '=== curl auth ==='
curl -sI https://cal.digitalehandwerkskunst.de/auth/login | head -12
echo '=== curl signup ==='
curl -sI https://cal.digitalehandwerkskunst.de/auth/setup | head -12
"""

client = paramiko.SSHClient()
ssh_connect(client, timeout=60, banner_timeout=60, role="web")
_, out, err = client.exec_command(cmd, timeout=60)
print((out.read() + err.read()).decode("utf-8", "replace"))
client.close()
