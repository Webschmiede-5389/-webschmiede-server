#!/usr/bin/env python3
"""Rewrite availability as one row per day (Cal.com style) + set link location."""
import os
import sys

import paramiko

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency_config import ssh_connect

SQL = r"""
BEGIN;

DELETE FROM "Availability" a
USING "Schedule" s
WHERE a."scheduleId" = s.id
  AND s.name = 'Do-Fr 14-18'
  AND a."eventTypeId" IS NULL
  AND a.date IS NULL;

-- Cal.com often stores one Availability row per weekday
INSERT INTO "Availability" ("scheduleId", "eventTypeId", "userId", days, "startTime", "endTime", date)
SELECT s.id, NULL, s."userId", ARRAY[d]::integer[], TIME '14:00', TIME '18:00', NULL
FROM "Schedule" s
CROSS JOIN (VALUES (4), (5)) AS days(d)
WHERE s.name = 'Do-Fr 14-18';

-- phone location so booking doesn't depend on Cal Video
UPDATE "EventType"
SET locations = '[{"type":"userPhone"}]'::jsonb,
    "updatedAt" = NOW()
WHERE slug = 'erstgespraech';

UPDATE "EventType"
SET locations = '[{"type":"userPhone"}]'::jsonb,
    "updatedAt" = NOW()
WHERE slug IN ('15min','30min') AND (locations IS NULL OR locations = '[]'::jsonb);

COMMIT;

SELECT a.id, a.days, a."startTime", a."endTime", a."userId", a."scheduleId"
FROM "Availability" a
JOIN "Schedule" s ON s.id = a."scheduleId"
WHERE s.name = 'Do-Fr 14-18';
"""

client = paramiko.SSHClient()
ssh_connect(client, timeout=60, banner_timeout=60, role="web")
sftp = client.open_sftp()
with sftp.file("/tmp/cal_avail_rows.sql", "w") as f:
    f.write(SQL)
sftp.close()
_, out, err = client.exec_command(
    "docker cp /tmp/cal_avail_rows.sql calcom-database-1:/tmp/cal_avail_rows.sql && "
    "docker exec calcom-database-1 psql -U cal -d calendso -v ON_ERROR_STOP=1 -f /tmp/cal_avail_rows.sql",
    timeout=60,
)
print((out.read() + err.read()).decode("utf-8", "replace"))

# Check recent calcom logs for slot errors
_, out, err = client.exec_command(
    "docker logs calcom-calcom-1 --tail 80 2>&1 | tr -cd '\\11\\12\\15\\40-\\176' | tail -60",
    timeout=30,
)
print("=== logs ===")
print((out.read() + err.read()).decode("utf-8", "replace")[-4000:])
client.close()
