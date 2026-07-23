#!/usr/bin/env python3
import os
import sys

import paramiko

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency_config import ssh_connect

SQL = r"""
SELECT id, email, username, name, "defaultScheduleId" FROM users;
SELECT count(*) AS schedules FROM "Schedule";
SELECT count(*) AS ets FROM "EventType";
SELECT count(*) AS avail FROM "Availability";
"""

client = paramiko.SSHClient()
ssh_connect(client, timeout=60, banner_timeout=60, role="web")
sftp = client.open_sftp()
with sftp.file("/tmp/cal_check.sql", "w") as f:
    f.write(SQL)
sftp.close()
_, out, err = client.exec_command(
    "docker cp /tmp/cal_check.sql calcom-database-1:/tmp/cal_check.sql && "
    "docker exec calcom-database-1 psql -U cal -d calendso -f /tmp/cal_check.sql",
    timeout=30,
)
print((out.read() + err.read()).decode("utf-8", "replace"))
client.close()
