#!/usr/bin/env python3
import os
import sys

import paramiko

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency_config import ssh_connect

SQL = r"""
BEGIN;

-- Link erstgespraech to user via many-to-many
INSERT INTO "_user_eventtype" ("A", "B")
SELECT e.id, u.id
FROM "EventType" e
CROSS JOIN users u
WHERE e.slug = 'erstgespraech'
  AND u.username = 'christian'
  AND NOT EXISTS (
    SELECT 1 FROM "_user_eventtype" x WHERE x."A" = e.id AND x."B" = u.id
  );

-- Match working event types: empty locations, usd, touch updatedAt
UPDATE "EventType"
SET locations = '[]'::jsonb,
    metadata = NULL,
    currency = 'usd',
    "updatedAt" = NOW()
WHERE slug = 'erstgespraech';

COMMIT;

SELECT e.id, e.slug, x."A", x."B"
FROM "EventType" e
LEFT JOIN "_user_eventtype" x ON x."A" = e.id
ORDER BY e.id;
"""

client = paramiko.SSHClient()
ssh_connect(client, timeout=60, banner_timeout=60, role="web")
sftp = client.open_sftp()
with sftp.file("/tmp/cal_fix_et.sql", "w") as f:
    f.write(SQL)
sftp.close()
_, out, err = client.exec_command(
    "docker cp /tmp/cal_fix_et.sql calcom-database-1:/tmp/cal_fix_et.sql && "
    "docker exec calcom-database-1 psql -U cal -d calendso -v ON_ERROR_STOP=1 -f /tmp/cal_fix_et.sql",
    timeout=60,
)
print((out.read() + err.read()).decode("utf-8", "replace"))
client.close()
