#!/usr/bin/env python3
"""Hide default Cal.com event types; keep only Erstgespräch public."""
import os
import sys

import paramiko

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency_config import ssh_connect

SQL = r"""
UPDATE "EventType"
SET hidden = true, "updatedAt" = NOW()
WHERE slug IN ('15min', '30min', 'secret')
  AND "userId" = (SELECT id FROM users WHERE username = 'christian');

SELECT slug, title, hidden FROM "EventType" ORDER BY id;
"""

client = paramiko.SSHClient()
ssh_connect(client, timeout=60, banner_timeout=60, role="web")
sftp = client.open_sftp()
with sftp.file("/tmp/cal_hide.sql", "w") as f:
    f.write(SQL)
sftp.close()
_, out, err = client.exec_command(
    "docker cp /tmp/cal_hide.sql calcom-database-1:/tmp/cal_hide.sql && "
    "docker exec calcom-database-1 psql -U cal -d calendso -v ON_ERROR_STOP=1 -f /tmp/cal_hide.sql",
    timeout=30,
)
print((out.read() + err.read()).decode("utf-8", "replace"))
client.close()
