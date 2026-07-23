#!/usr/bin/env python3
"""Ensure all event types use Do-Fr schedule; verify availability."""
import os
import sys

import paramiko

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency_config import ssh_connect

SQL = r"""
UPDATE "EventType" e
SET "scheduleId" = s.id
FROM "Schedule" s
JOIN users u ON u.id = s."userId"
WHERE e."userId" = u.id
  AND u.username = 'christian'
  AND s.name = 'Do-Fr 14-18';

-- If onboarding created another schedule with Mon-Fri defaults, prune extra weekly slots
DELETE FROM "Availability" a
USING "Schedule" s, users u
WHERE a."scheduleId" = s.id
  AND s."userId" = u.id
  AND u.username = 'christian'
  AND a."eventTypeId" IS NULL
  AND a.date IS NULL
  AND s.name <> 'Do-Fr 14-18';

-- Keep only one availability row on Do-Fr schedule
DELETE FROM "Availability" a
USING "Schedule" s, users u
WHERE a."scheduleId" = s.id
  AND s."userId" = u.id
  AND u.username = 'christian'
  AND s.name = 'Do-Fr 14-18'
  AND a.id NOT IN (
    SELECT MIN(a2.id) FROM "Availability" a2
    WHERE a2."scheduleId" = s.id AND a2."eventTypeId" IS NULL AND a2.date IS NULL
  );

SELECT s.id, s.name, s."timeZone", a.days, a."startTime", a."endTime"
FROM "Schedule" s
LEFT JOIN "Availability" a ON a."scheduleId" = s.id
JOIN users u ON u.id = s."userId"
WHERE u.username = 'christian'
ORDER BY s.id, a.id;

SELECT id, title, slug, "scheduleId", hidden FROM "EventType" ORDER BY id;
"""

client = paramiko.SSHClient()
ssh_connect(client, timeout=60, banner_timeout=60, role="web")
sftp = client.open_sftp()
with sftp.file("/tmp/cal_attach.sql", "w") as f:
    f.write(SQL)
sftp.close()
_, out, err = client.exec_command(
    "docker cp /tmp/cal_attach.sql calcom-database-1:/tmp/cal_attach.sql && "
    "docker exec calcom-database-1 psql -U cal -d calendso -v ON_ERROR_STOP=1 -f /tmp/cal_attach.sql",
    timeout=60,
)
print((out.read() + err.read()).decode("utf-8", "replace"))
client.close()
