#!/usr/bin/env python3
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
systemctl cat snack-api | sed -n '1,40p'
echo '---'
for py in /root/app/backend/venv/bin/python /root/app/venv/bin/python /usr/bin/python3; do
  if [ -x "$py" ]; then echo "PY=$py"; "$py" -c 'import sys; print(sys.executable)'; break; fi
done
PY=$(command -v /root/app/backend/venv/bin/python || command -v /root/app/venv/bin/python || echo python3)
cd /root/app/backend
$PY - <<'PY'
import sys
print('exe', sys.executable)
try:
    import stripe
    print('stripe', True)
except Exception as e:
    print('stripe', False, type(e).__name__)
try:
    import telegram_agent
    print('telegram_agent', True)
except Exception as e:
    print('telegram_agent', False, e)
PY
# notify anyway
python3 - <<'PY'
from pathlib import Path
import json, urllib.request
vals={}
for line in Path('/root/app/backend/.env').read_text(errors='replace').splitlines():
    if '=' in line and not line.strip().startswith('#'):
        k,v=line.split('=',1); vals[k.strip()]=v.strip().strip('"').strip("'")
text=(
 'Agency-Hirn Upgrade live.\n'
 'Modell: qwen2.5:14b (Ollama).\n'
 'Ansprechen:\n'
 '- nils: Dual Status\n'
 '- stefan: Naechster Umsatz-Schritt?\n'
 '- Alle Kunden / Status SHY001 / Deals\n'
 'Mails/Angebote: erst nach ja.\n'
 'Kein Repo-Edit wie Cursor.'
)
payload=json.dumps({'chat_id': vals.get('TELEGRAM_OWNER_CHAT_ID','').split(',')[0],'text':text}).encode()
req=urllib.request.Request(f"https://api.telegram.org/bot{vals.get('TELEGRAM_BOT_TOKEN')}/sendMessage", data=payload, headers={'Content-Type':'application/json'})
with urllib.request.urlopen(req, timeout=20) as r:
    print('tg', json.loads(r.read().decode()).get('ok'))
PY
"""
_, o, e = c.exec_command(cmd)
print(o.read().decode(errors="replace"))
print(e.read().decode(errors="replace")[:600])
c.close()
