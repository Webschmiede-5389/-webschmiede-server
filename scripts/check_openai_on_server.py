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
import os, json, urllib.request
vals={}
for p in (Path('/root/app/deploy.secrets.local'), Path('/root/app/backend/.env')):
    if not p.exists(): continue
    for line in p.read_text(errors='replace').splitlines():
        s=line.strip()
        if not s or s.startswith('#') or '=' not in s: continue
        k,v=s.split('=',1)
        vals.setdefault(k.strip(), v.strip().strip('"').strip("'"))
key=(vals.get('OPENAI_API_KEY') or '').strip()
print('openai_in_files', bool(key), 'len', len(key))
# process env via systemd EnvironmentFile
env_path=Path('/root/app/backend/.env')
in_env=False
if env_path.exists():
    for line in env_path.read_text(errors='replace').splitlines():
        if line.startswith('OPENAI_API_KEY=') and len(line.split('=',1)[1].strip())>10:
            in_env=True
print('openai_in_backend_env', in_env)
if key:
    # sync to .env if missing
    if not in_env:
        with env_path.open('a', encoding='utf-8') as f:
            f.write(f'\nOPENAI_API_KEY={key}\n')
        print('synced_to_env', True)
    req=urllib.request.Request(
        'https://api.openai.com/v1/models',
        headers={'Authorization': f'Bearer {key}'},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            print('openai_api', r.status)
    except Exception as e:
        print('openai_api_error', str(e)[:120])
PY
systemctl restart snack-api
sleep 2
systemctl is-active snack-api
"""
_, o, e = c.exec_command(cmd)
print(o.read().decode())
print(e.read().decode())
c.close()
