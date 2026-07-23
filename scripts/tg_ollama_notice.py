#!/usr/bin/env python3
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import paramiko
from agency_config import ssh_connect

c = paramiko.SSHClient()
ssh_connect(c, timeout=15, banner_timeout=15, role="web")
cmd = r"""
python3 - <<'PY'
from pathlib import Path
import json, urllib.request
vals = {}
for line in Path('/root/app/backend/.env').read_text(errors='replace').splitlines():
    if '=' in line and not line.strip().startswith('#'):
        k, v = line.split('=', 1)
        vals[k.strip()] = v.strip().strip('"').strip("'")
token = vals.get('TELEGRAM_BOT_TOKEN', '')
chat = (vals.get('TELEGRAM_OWNER_CHAT_ID') or '').split(',')[0]
text = (
    'Nils hier. Ollama (gratis, auto-01) ist jetzt angebunden. '
    'Schreib mir einfach normal. '
    'Aktuell llama3.2:1b (klein). Fuer schaerfere Antworten koennen wir spaeter 3b pullen.'
)
payload = json.dumps({'chat_id': chat, 'text': text, 'disable_web_page_preview': True}).encode()
req = urllib.request.Request(
    f'https://api.telegram.org/bot{token}/sendMessage',
    data=payload,
    headers={'Content-Type': 'application/json'},
)
with urllib.request.urlopen(req, timeout=20) as r:
    print('telegram_ok', json.loads(r.read().decode()).get('ok'))
PY
"""
_, o, e = c.exec_command(cmd)
print(o.read().decode(errors="replace"))
print(e.read().decode(errors="replace")[:300])
c.close()
