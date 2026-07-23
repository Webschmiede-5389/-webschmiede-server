#!/usr/bin/env python3
"""Smoke telegram_agent on web + Telegram notice."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import paramiko
from agency_config import ssh_connect

c = paramiko.SSHClient()
ssh_connect(c, timeout=20, banner_timeout=20, role="web")
cmd = r"""
cd /root/app/backend
python3 - <<'PY'
import os, sqlite3
from pathlib import Path
for line in Path('/root/app/backend/.env').read_text(errors='replace').splitlines():
    if '=' in line and not line.strip().startswith('#'):
        k,v=line.split('=',1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
print('model', os.getenv('OLLAMA_MODEL'))
import telegram_agent as ag
db = sqlite3.connect('/root/app/backend/orders.db')
db.row_factory = sqlite3.Row
r = ag.handle(db, 'Alle Kunden')
print('route', r.get('route'), 'tools', r.get('tools'))
print('reply', (r.get('reply') or '')[:400])
# telegram notice
import json, urllib.request
vals={}
for line in Path('/root/app/backend/.env').read_text(errors='replace').splitlines():
    if '=' in line and not line.strip().startswith('#'):
        k,v=line.split('=',1); vals[k.strip()]=v.strip().strip('"').strip("'")
text = (
  'Agency-Hirn Upgrade live.\n'
  'Modell: qwen2.5:14b (Ollama, gratis).\n'
  'Du kannst Nils und Stefan ansprechen:\n'
  '• nils: Dual Status\n'
  '• stefan: Was ist der naechste Umsatz-Schritt?\n'
  '• Alle Kunden / Status SHY001 / Deals\n'
  'Mails und Angebote fragen nach ja.\n'
  'Kein Repo-Edit wie Cursor, dafuer Ops+Strategie+Tools.'
)
payload=json.dumps({'chat_id': vals.get('TELEGRAM_OWNER_CHAT_ID','').split(',')[0], 'text': text}).encode()
req=urllib.request.Request(
  f"https://api.telegram.org/bot{vals.get('TELEGRAM_BOT_TOKEN')}/sendMessage",
  data=payload, headers={'Content-Type':'application/json'})
with urllib.request.urlopen(req, timeout=20) as resp:
  print('tg', json.loads(resp.read().decode()).get('ok'))
db.close()
PY
"""
_, o, e = c.exec_command(cmd)
print(o.read().decode(errors="replace"))
err = e.read().decode(errors="replace")
if err.strip():
    print(err[:800], file=sys.stderr)
c.close()
