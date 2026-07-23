#!/usr/bin/env python3
"""Create Do/Fr 14-18 schedule + Erstgespräch event type (correct schema)."""
import os
import sys

import paramiko

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency_config import ssh_connect

SQL = r"""
BEGIN;

INSERT INTO "Schedule" (name, "timeZone", "userId")
SELECT 'Do-Fr 14-18', 'Europe/Berlin', u.id
FROM users u
WHERE u.username = 'christian'
  AND NOT EXISTS (SELECT 1 FROM "Schedule" s WHERE s."userId" = u.id);

UPDATE "Schedule"
SET name = 'Do-Fr 14-18', "timeZone" = 'Europe/Berlin'
WHERE "userId" = (SELECT id FROM users WHERE username = 'christian');

DELETE FROM "Availability" a
USING "Schedule" s
WHERE a."scheduleId" = s.id
  AND s."userId" = (SELECT id FROM users WHERE username = 'christian')
  AND a."eventTypeId" IS NULL
  AND a.date IS NULL;

INSERT INTO "Availability" ("scheduleId", "eventTypeId", "userId", days, "startTime", "endTime", date)
SELECT s.id, NULL, s."userId", ARRAY[4,5]::integer[], TIME '14:00', TIME '18:00', NULL
FROM "Schedule" s
WHERE s."userId" = (SELECT id FROM users WHERE username = 'christian')
ORDER BY s.id
LIMIT 1;

UPDATE users
SET "defaultScheduleId" = (
  SELECT id FROM "Schedule" WHERE "userId" = users.id ORDER BY id LIMIT 1
),
"timeZone" = 'Europe/Berlin'
WHERE username = 'christian';

INSERT INTO "EventType" (
  title, slug, description, length, "userId", "scheduleId",
  hidden, "periodType", "requiresConfirmation", "disableGuests",
  "hideCalendarNotes", "minimumBookingNotice", "beforeEventBuffer", "afterEventBuffer",
  locations, metadata, currency, price,
  "requiresBookerEmailVerification", "isInstantEvent", "assignAllTeamMembers"
)
SELECT
  'Kostenloses Erstgespräch',
  'erstgespraech',
  '30 Minuten Kennenlernen – Do/Fr 14–18 Uhr (Europe/Berlin)',
  30,
  u.id,
  s.id,
  false,
  'unlimited'::"PeriodType",
  false,
  false,
  false,
  60,
  0,
  0,
  '[{"type":"integrations:daily"}]'::jsonb,
  '{}'::jsonb,
  'eur',
  0,
  false,
  false,
  false
FROM users u
JOIN "Schedule" s ON s."userId" = u.id
WHERE u.username = 'christian'
  AND NOT EXISTS (
    SELECT 1 FROM "EventType" e WHERE e."userId" = u.id AND e.slug = 'erstgespraech'
  )
LIMIT 1;

-- attach any other event types to this schedule
UPDATE "EventType" e
SET "scheduleId" = s.id
FROM "Schedule" s
WHERE e."userId" = s."userId"
  AND s."userId" = (SELECT id FROM users WHERE username = 'christian')
  AND (e."scheduleId" IS NULL OR e."scheduleId" <> s.id);

COMMIT;

SELECT u.username, u."defaultScheduleId", u."timeZone", s.name, s."timeZone" AS sched_tz,
       a.days, a."startTime", a."endTime"
FROM users u
LEFT JOIN "Schedule" s ON s.id = u."defaultScheduleId"
LEFT JOIN "Availability" a ON a."scheduleId" = s.id
WHERE u.username = 'christian';

SELECT id, title, slug, length, "scheduleId" FROM "EventType";
"""

client = paramiko.SSHClient()
ssh_connect(client, timeout=60, banner_timeout=60, role="web")
sftp = client.open_sftp()
with sftp.file("/tmp/cal_hours_ok.sql", "w") as f:
    f.write(SQL)
sftp.close()
_, out, err = client.exec_command(
    "docker cp /tmp/cal_hours_ok.sql calcom-database-1:/tmp/cal_hours_ok.sql && "
    "docker exec calcom-database-1 psql -U cal -d calendso -v ON_ERROR_STOP=1 -f /tmp/cal_hours_ok.sql",
    timeout=60,
)
print((out.read() + err.read()).decode("utf-8", "replace"))
client.close()
