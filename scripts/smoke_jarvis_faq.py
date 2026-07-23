#!/usr/bin/env python3
"""Smoke: Jarvis Knowledge FAQ (direkt auf dem Server)."""
import json
import sys

import paramiko

sys.path.insert(0, ".")
from agency_config import ssh_connect

REMOTE = r"""
import sqlite3, sys, json
sys.path.insert(0, '/root/app')
from jarvis import bot
db = sqlite3.connect('/root/app/backend/orders.db')
r = bot.handle_message(db, '+4924433088966', 'wann habt ihr offen', client_id='SHY001', channel='test')
print(json.dumps(r, ensure_ascii=False))
"""

client = paramiko.SSHClient()
ssh_connect(client, role="web")
client.exec_command("cat > /tmp/smoke_jarvis_faq.py << 'PYEOF'\n" + REMOTE + "\nPYEOF")
_, out, err = client.exec_command("/root/app/venv/bin/python3 /tmp/smoke_jarvis_faq.py", timeout=30)
body = out.read().decode().strip()
errb = err.read().decode().strip()
if errb:
    print("ERR:", errb[:400])
if not body:
    raise SystemExit("empty response")
print(body)
data = json.loads(body)
assert data.get("success"), data
assert data.get("faq_id") == "oeffnungszeiten", data
print("OK jarvis FAQ:", data.get("faq_id"))
client.close()
