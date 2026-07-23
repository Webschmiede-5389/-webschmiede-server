#!/usr/bin/env python3
import os
import sys

import paramiko

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency_config import ssh_connect

SQL = r"""
\d users
SELECT id, username, email, name, "completedOnboarding", "timeZone", "defaultScheduleId", "allowDynamicBooking", "disableBookingPage" FROM users;
SELECT * FROM "Profile" LIMIT 10;
SELECT id, slug, "userId", "teamId", hidden FROM "EventType";
"""

client = paramiko.SSHClient()
ssh_connect(client, timeout=60, banner_timeout=60, role="web")
sftp = client.open_sftp()
with sftp.file("/tmp/cal_profile.sql", "w") as f:
    f.write(SQL)
sftp.close()
_, out, err = client.exec_command(
    "docker cp /tmp/cal_profile.sql calcom-database-1:/tmp/cal_profile.sql && "
    "docker exec calcom-database-1 psql -U cal -d calendso -f /tmp/cal_profile.sql",
    timeout=60,
)
print((out.read() + err.read()).decode("utf-8", "replace")[:12000])
client.close()
