#!/usr/bin/env python3
"""Send Telegram test that LLM path works (via nils_ops on server)."""
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
cd /root/app/backend
python3 - <<'PY'
import os, sqlite3
from pathlib import Path
# load env
for line in Path('/root/app/backend/.env').read_text(errors='replace').splitlines():
    if '=' in line and not line.strip().startswith('#'):
        k,v=line.split('=',1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
import llm_client as llm
print('readiness', llm.readiness())
r = llm.chat([
    {'role':'system','content':'Du bist Nils. Antworte auf Deutsch in max 2 kurzen Saetzen. Kein Englisch.'},
    {'role':'user','content':'Kurzer Test: bist du jetzt ueber Ollama erreichbar? Sag ja und einen naechsten Schritt.'},
], max_tokens=120, temperature=0.4, timeout=90)
print('provider', r.get('provider'), 'ok', r.get('ok'))
print('reply', (r.get('reply') or r.get('error') or '')[:300])
import telegram_ops as tg
if r.get('ok') and r.get('reply'):
    ping = tg.notify_owner('Nils · Ollama live.\n\n' + r['reply'][:800])
    print('telegram', ping.get('ok'))
else:
    print('telegram_skip')
PY
"""
_, o, e = c.exec_command(cmd)
print(o.read().decode(errors='replace'))
print(e.read().decode(errors='replace')[:400])
c.close()
