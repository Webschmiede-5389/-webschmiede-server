#!/usr/bin/env python3
import os
import sys

import paramiko

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency_config import ssh_connect

SQL = r"""
SELECT * FROM "EventType" WHERE slug IN ('erstgespraech','15min') ORDER BY slug;
\d "_user_eventtype"
SELECT * FROM "_user_eventtype";
"""

client = paramiko.SSHClient()
ssh_connect(client, timeout=60, banner_timeout=60, role="web")
sftp = client.open_sftp()
with sftp.file("/tmp/cal_et_cmp.sql", "w") as f:
    f.write(SQL)
sftp.close()
_, out, err = client.exec_command(
    "docker cp /tmp/cal_et_cmp.sql calcom-database-1:/tmp/cal_et_cmp.sql && "
    "docker exec calcom-database-1 psql -U cal -d calendso -x -f /tmp/cal_et_cmp.sql 2>&1",
    timeout=60,
)
print((out.read() + err.read()).decode("utf-8", "replace")[:15000])
client.close()
