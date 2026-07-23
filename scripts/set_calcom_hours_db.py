#!/usr/bin/env python3
"""Set Cal.com availability via Postgres (self-hosted) when API is broken."""
import os
import sys

import paramiko

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency_config import ssh_connect

REMOTE = r'''
set -e
echo "=== calcom containers ==="
docker ps -a --format '{{.Names}} {{.Status}}' | grep -i cal || true
echo "=== v2 api log ==="
docker logs calcom-calcom-1 --tail 40 2>&1 | tr -cd '\11\12\15\40-\176' | tail -40
echo "=== db ==="
DB=$(docker ps --format '{{.Names}}' | grep -i calcom | grep -iE 'db|postgres|database' | head -1)
echo "DBCONT=$DB"
if [ -z "$DB" ]; then
  # try compose service
  DB=$(docker ps --format '{{.Names}}' | grep -i cal | head -1)
fi
# Find postgres container for calcom
for c in $(docker ps --format '{{.Names}}'); do
  echo "$c"
done
'''

SQL = r'''
-- Cal.com: only Thu+Fri 14:00-18:00 Europe/Berlin
-- days: 0=Sun ... 4=Thu 5=Fri 6=Sat
BEGIN;

-- ensure at least one schedule
WITH u AS (
  SELECT id FROM users ORDER BY id ASC LIMIT 1
), s AS (
  SELECT id, "userId" FROM "Schedule" ORDER BY id ASC LIMIT 1
)
SELECT 1;

UPDATE "Schedule"
SET "timeZone" = 'Europe/Berlin',
    name = 'Do-Fr 14-18'
WHERE id = (SELECT id FROM "Schedule" ORDER BY id ASC LIMIT 1);

-- remove existing weekly availability rows for default schedule (eventTypeId null)
DELETE FROM "Availability"
WHERE "scheduleId" = (SELECT id FROM "Schedule" ORDER BY id ASC LIMIT 1)
  AND "eventTypeId" IS NULL
  AND date IS NULL;

INSERT INTO "Availability" ("scheduleId", "eventTypeId", "userId", days, "startTime", "endTime", date)
SELECT
  s.id,
  NULL,
  s."userId",
  ARRAY[4,5]::integer[],
  TIME '14:00',
  TIME '18:00',
  NULL
FROM "Schedule" s
ORDER BY s.id ASC
LIMIT 1;

-- mark default
UPDATE "users"
SET "defaultScheduleId" = (SELECT id FROM "Schedule" ORDER BY id ASC LIMIT 1)
WHERE id = (SELECT "userId" FROM "Schedule" ORDER BY id ASC LIMIT 1);

COMMIT;

SELECT s.id, s.name, s."timeZone", a.days, a."startTime", a."endTime"
FROM "Schedule" s
LEFT JOIN "Availability" a ON a."scheduleId" = s.id
ORDER BY s.id, a.id;
'''

client = paramiko.SSHClient()
ssh_connect(client, timeout=60, banner_timeout=60, role="web")


def run(cmd: str, timeout: int = 120) -> str:
    _, out, err = client.exec_command(cmd, timeout=timeout)
    text = (out.read() + err.read()).decode("utf-8", "replace")
    print(text)
    return text


run(REMOTE)

# discover db container and credentials from compose
info = run(
    "grep -E 'POSTGRES_|DATABASE_URL' /opt/calcom/docker-compose.yml 2>/dev/null | head -30; "
    "docker ps --format '{{.Names}}' | grep -iE 'cal|postgres'"
)

# Write SQL to remote and execute via docker exec
sftp = client.open_sftp()
with sftp.file("/tmp/cal_hours.sql", "w") as f:
    f.write(SQL)
sftp.close()

# Try common calcom db container names
run(
    """
set -e
DBCONT=$(docker ps --format '{{.Names}}' | grep -iE 'calcom.*database|calcom.*postgres|calcom-db' | head -1)
echo DBCONT=$DBCONT
if [ -n "$DBCONT" ]; then
  docker cp /tmp/cal_hours.sql "$DBCONT":/tmp/cal_hours.sql
  # user/db from env
  U=$(docker exec "$DBCONT" printenv POSTGRES_USER 2>/dev/null || echo postgres)
  D=$(docker exec "$DBCONT" printenv POSTGRES_DB 2>/dev/null || echo calcom)
  echo USER=$U DB=$D
  docker exec -i "$DBCONT" psql -U "$U" -d "$D" -v ON_ERROR_STOP=1 -f /tmp/cal_hours.sql
else
  echo NO_DB_CONTAINER
  # try from calcom app DATABASE_URL
  URL=$(docker exec calcom-calcom-1 printenv DATABASE_URL 2>/dev/null || true)
  echo DATABASE_URL_SET=$([ -n "$URL" ] && echo yes || echo no)
fi
""",
    timeout=180,
)
client.close()
