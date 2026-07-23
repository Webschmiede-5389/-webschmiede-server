#!/usr/bin/env python3
import os
import sys

import paramiko

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency_config import ssh_connect

SQL = r"""
SELECT id, username, email, name, "completedOnboarding", "timeZone", "defaultScheduleId", "allowDynamicBooking", role FROM users;
\d "Profile"
SELECT * FROM "Profile";
SELECT id, slug, title, "userId", "profileId", "teamId", hidden FROM "EventType";
SELECT id, slug FROM "_user_eventtype";
"""

client = paramiko.SSHClient()
ssh_connect(client, timeout=60, banner_timeout=60, role="web")
sftp = client.open_sftp()
with sftp.file("/tmp/cal_profile2.sql", "w") as f:
    f.write(SQL)
sftp.close()
_, out, err = client.exec_command(
    "docker cp /tmp/cal_profile2.sql calcom-database-1:/tmp/cal_profile2.sql && "
    "docker exec calcom-database-1 psql -U cal -d calendso -f /tmp/cal_profile2.sql 2>&1 | tail -80",
    timeout=60,
)
print((out.read() + err.read()).decode("utf-8", "replace"))
client.close()
