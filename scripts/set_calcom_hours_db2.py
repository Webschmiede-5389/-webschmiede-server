#!/usr/bin/env python3
"""Inspect Cal.com DB schema + create Do/Fr 14-18 schedule."""
import os
import sys

import paramiko

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency_config import ssh_connect

INSPECT = r'''
docker exec calcom-database-1 psql -U cal -d calendso -c "\dt" 
docker exec calcom-database-1 psql -U cal -d calendso -c "SELECT id, email, username, name, \"defaultScheduleId\" FROM users LIMIT 10;"
docker exec calcom-database-1 psql -U cal -d calendso -c "\d \"Schedule\""
docker exec calcom-database-1 psql -U cal -d calendso -c "\d \"Availability\""
docker exec calcom-database-1 psql -U cal -d calendso -c "SELECT id, title, slug, \"scheduleId\", length FROM \"EventType\" LIMIT 20;"
'''

CREATE = r'''
BEGIN;

-- pick first user
DO $$
DECLARE
  uid INTEGER;
  sid INTEGER;
BEGIN
  SELECT id INTO uid FROM users ORDER BY id ASC LIMIT 1;
  IF uid IS NULL THEN
    RAISE EXCEPTION 'no user';
  END IF;

  -- create schedule if missing
  SELECT id INTO sid FROM "Schedule" WHERE "userId" = uid ORDER BY id ASC LIMIT 1;
  IF sid IS NULL THEN
    INSERT INTO "Schedule" (name, "timeZone", "userId")
    VALUES ('Do-Fr 14-18', 'Europe/Berlin', uid)
    RETURNING id INTO sid;
  ELSE
    UPDATE "Schedule"
    SET name = 'Do-Fr 14-18', "timeZone" = 'Europe/Berlin'
    WHERE id = sid;
  END IF;

  DELETE FROM "Availability"
  WHERE "scheduleId" = sid
    AND "eventTypeId" IS NULL
    AND date IS NULL;

  INSERT INTO "Availability" ("scheduleId", "eventTypeId", "userId", days, "startTime", "endTime", date)
  VALUES (sid, NULL, uid, ARRAY[4,5]::integer[], TIME '14:00', TIME '18:00', NULL);

  UPDATE users SET "defaultScheduleId" = sid WHERE id = uid;

  -- attach schedule to event types without one
  UPDATE "EventType" SET "scheduleId" = sid WHERE "userId" = uid AND ("scheduleId" IS NULL OR "scheduleId" <> sid);

  RAISE NOTICE 'user=% schedule=%', uid, sid;
END $$;

COMMIT;

SELECT u.id AS user_id, u.email, u.username, u."defaultScheduleId",
       s.id AS schedule_id, s.name, s."timeZone"
FROM users u
LEFT JOIN "Schedule" s ON s.id = u."defaultScheduleId"
ORDER BY u.id;

SELECT a.id, a."scheduleId", a.days, a."startTime", a."endTime", a."userId"
FROM "Availability" a
ORDER BY a.id;

SELECT id, title, slug, "scheduleId", length FROM "EventType" ORDER BY id;
'''

client = paramiko.SSHClient()
ssh_connect(client, timeout=60, banner_timeout=60, role="web")


def run(cmd: str, timeout: int = 120) -> str:
    _, out, err = client.exec_command(cmd, timeout=timeout)
    text = (out.read() + err.read()).decode("utf-8", "replace")
    print(text)
    return text


print("=== INSPECT ===")
run(INSPECT, timeout=60)

sftp = client.open_sftp()
with sftp.file("/tmp/cal_create_hours.sql", "w") as f:
    f.write(CREATE)
sftp.close()

print("=== CREATE ===")
run(
    "docker cp /tmp/cal_create_hours.sql calcom-database-1:/tmp/cal_create_hours.sql && "
    "docker exec calcom-database-1 psql -U cal -d calendso -v ON_ERROR_STOP=1 -f /tmp/cal_create_hours.sql",
    timeout=60,
)
client.close()
