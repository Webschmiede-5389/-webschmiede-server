#!/usr/bin/env python3
"""Update Cal.com Erstgespräch copy to match site CTA."""
import os
import sys

import paramiko

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency_config import ssh_connect

SQL = r"""
UPDATE "EventType"
SET
  title = 'Kostenloses Gespräch',
  description = '15–30 Minuten Orientierung: Was hängt in Ihrem Betrieb? Systeme, Automatisierung, Datenhaltung in Deutschland. Kein Verkaufsmarathon. Do/Fr 14–18 Uhr (Europe/Berlin).',
  "updatedAt" = NOW()
WHERE slug = 'erstgespraech';

SELECT id, title, slug, left(description, 120) AS desc_preview FROM "EventType" WHERE slug = 'erstgespraech';
"""

client = paramiko.SSHClient()
ssh_connect(client, timeout=60, banner_timeout=60, role="web")
sftp = client.open_sftp()
with sftp.file("/tmp/cal_copy.sql", "w") as f:
    f.write(SQL)
sftp.close()
_, out, err = client.exec_command(
    "docker cp /tmp/cal_copy.sql calcom-database-1:/tmp/cal_copy.sql && "
    "docker exec calcom-database-1 psql -U cal -d calendso -v ON_ERROR_STOP=1 -f /tmp/cal_copy.sql",
    timeout=30,
)
print((out.read() + err.read()).decode("utf-8", "replace"))

# Ensure SPA fallback for /anbindungen
_, out, err = client.exec_command(
    "grep -n 'try_files\\|digitalehandwerkskunst' /etc/nginx/sites-enabled/* 2>/dev/null | head -40; "
    "ls /etc/nginx/sites-enabled/ 2>/dev/null",
    timeout=20,
)
print("=== nginx ===")
print((out.read() + err.read()).decode("utf-8", "replace")[:3000])
client.close()
