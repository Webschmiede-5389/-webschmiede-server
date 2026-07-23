#!/usr/bin/env python3
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import paramiko
from agency_config import ssh_connect

client = paramiko.SSHClient()
ssh_connect(client, timeout=15, banner_timeout=15, role="web")
cmd = r"""
systemctl restart snack-api
sleep 2
systemctl is-active snack-api
python3 - <<'PY'
from pathlib import Path
import json, urllib.request
vals = {}
for p in (Path('/root/app/deploy.secrets.local'), Path('/root/app/backend/.env')):
    if not p.exists():
        continue
    for line in p.read_text(errors='replace').splitlines():
        s = line.strip()
        if not s or s.startswith('#') or '=' not in s:
            continue
        k, v = s.split('=', 1)
        vals.setdefault(k.strip(), v.strip().strip('"').strip("'"))
t = vals.get('TELEGRAM_BOT_TOKEN') or ''
with urllib.request.urlopen(f'https://api.telegram.org/bot{t}/getWebhookInfo', timeout=15) as r:
    info = json.loads(r.read().decode()).get('result') or {}
print('webhook', (info.get('url') or '')[:120])
print('pending', info.get('pending_update_count'))
print('last_error', (info.get('last_error_message') or '')[:160])
# process env check
import subprocess
out = subprocess.check_output(['systemctl', 'show', 'snack-api', '-p', 'EnvironmentFiles', '--value'], text=True)
print('env_files', out.strip()[:80])
PY
"""
_, stdout, stderr = client.exec_command(cmd)
print(stdout.read().decode("utf-8", errors="replace"))
err = stderr.read().decode("utf-8", errors="replace")
if err.strip():
    print(err, file=sys.stderr)
client.close()
