#!/usr/bin/env python3
"""Create schedule Do/Fr 14-18 + Erstgespräch event type for Cal.com user christian."""
import os
import sys

import paramiko

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency_config import ssh_connect

SQL = r"""
BEGIN;

-- Schedule
INSERT INTO "Schedule" (name, "timeZone", "userId")
SELECT 'Do-Fr 14-18', 'Europe/Berlin', u.id
FROM users u
WHERE u.username = 'christian'
  AND NOT EXISTS (SELECT 1 FROM "Schedule" s WHERE s."userId" = u.id)
RETURNING id;

UPDATE "Schedule"
SET name = 'Do-Fr 14-18', "timeZone" = 'Europe/Berlin'
WHERE "userId" = (SELECT id FROM users WHERE username = 'christian');

-- wipe weekly availability for schedule
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
  SELECT id FROM "Schedule"
  WHERE "userId" = users.id
  ORDER BY id LIMIT 1
),
"timeZone" = 'Europe/Berlin',
"weekStart" = 'Monday'
WHERE username = 'christian';

-- Create event type if missing (minimal columns)
-- Inspect required columns first via separate query if this fails
INSERT INTO "EventType" (
  title, slug, description, length, "userId", "scheduleId",
  hidden, "periodType", "requiresConfirmation", "disableGuests",
  "hideCalendarNotes", "minimumBookingNotice", "beforeEventBuffer", "afterEventBuffer",
  "seatsPerTimeSlot", "schedulingType", locations, metadata, "successRedirectUrl",
  "bookingRequiresAuthentication", "bookingRequiresVerification", "isInstantEvent",
  "assignAllTeamMembers", "useEventLevelSelectedCalendars", "requiresBookerEmailVerification"
)
SELECT
  'Kostenloses Erstgespräch',
  'erstgespraech',
  '30 Minuten Kennenlernen – Do/Fr 14–18 Uhr',
  30,
  u.id,
  s.id,
  false,
  'UNLIMITED'::"PeriodType",
  false,
  false,
  false,
  60,
  0,
  0,
  NULL,
  NULL,
  '[{"type":"integrations:daily"}]'::jsonb,
  '{}'::jsonb,
  NULL,
  false,
  false,
  false,
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

COMMIT;

SELECT u.username, u."defaultScheduleId", u."timeZone", s.name, a.days, a."startTime", a."endTime"
FROM users u
LEFT JOIN "Schedule" s ON s.id = u."defaultScheduleId"
LEFT JOIN "Availability" a ON a."scheduleId" = s.id
WHERE u.username = 'christian';

SELECT id, title, slug, length, "scheduleId" FROM "EventType";
"""

client = paramiko.SSHClient()
ssh_connect(client, timeout=60, banner_timeout=60, role="web")

# First dump EventType columns for accurate insert
_, out, err = client.exec_command(
    'docker exec calcom-database-1 psql -U cal -d calendso -c "\\d \\"EventType\\""',
    timeout=30,
)
print("=== EventType schema ===")
print((out.read() + err.read()).decode("utf-8", "replace")[:6000])

sftp = client.open_sftp()
with sftp.file("/tmp/cal_hours_final.sql", "w") as f:
    f.write(SQL)
sftp.close()

_, out, err = client.exec_command(
    "docker cp /tmp/cal_hours_final.sql calcom-database-1:/tmp/cal_hours_final.sql && "
    "docker exec calcom-database-1 psql -U cal -d calendso -v ON_ERROR_STOP=1 -f /tmp/cal_hours_final.sql",
    timeout=60,
)
print("=== apply ===")
print((out.read() + err.read()).decode("utf-8", "replace"))
client.close()
