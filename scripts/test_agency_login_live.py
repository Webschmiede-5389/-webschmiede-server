#!/usr/bin/env python3
"""Live-Test Agency-Login ohne Passwort auszugeben."""
import json
import os
import sys
import urllib.error
import urllib.request

import paramiko

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency_config import ssh_connect

client = paramiko.SSHClient()
ssh_connect(client, timeout=45, banner_timeout=45, role="web")


def run(cmd: str) -> str:
    _, out, err = client.exec_command(cmd, timeout=60)
    return (out.read() + err.read()).decode("utf-8", "replace").strip()


REMOTE = r"""
from pathlib import Path
import json, sqlite3, urllib.request
from werkzeug.security import check_password_hash

vals = {}
for p in (Path('/root/app/deploy.secrets.local'), Path('/root/app/backend/.env')):
    if p.exists():
        for line in p.read_text(encoding='utf-8', errors='replace').splitlines():
            if '=' in line and not line.strip().startswith('#'):
                k,v = line.split('=',1)
                vals[k.strip()] = v.strip()
pw = (vals.get('AGENCY_ADMIN_PASSWORD') or '').strip()
print('pw_len', len(pw))
print('pw_set', bool(pw))

con = sqlite3.connect('/root/app/backend/orders.db')
con.row_factory = sqlite3.Row
u = con.execute("SELECT * FROM portal_users WHERE username='christian' COLLATE NOCASE").fetchone()
print('user_found', bool(u))
if u:
    print('role', u['role'])
    print('hash_ok', check_password_hash(u['password_hash'], pw) if pw else False)
    print('email', u['email'])
    print('totp', u['totp_enabled'])

# local API via gunicorn
import urllib.request
body = json.dumps({'username':'christian','password':pw}).encode()
req = urllib.request.Request('http://127.0.0.1:8000/api/agency/login', data=body, headers={'Content-Type':'application/json'}, method='POST')
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        data = r.read().decode()
        print('local_http', r.status)
        print('local_body', data[:200])
except Exception as e:
    print('local_err', type(e).__name__, getattr(e, 'code', ''), str(e)[:200])
    if hasattr(e, 'read'):
        try:
            print('local_err_body', e.read().decode()[:200])
        except Exception:
            pass

# via nginx host digitalehandwerkskunst
req2 = urllib.request.Request(
    'http://127.0.0.1/api/agency/login',
    data=body,
    headers={'Content-Type':'application/json','Host':'digitalehandwerkskunst.de'},
    method='POST',
)
try:
    with urllib.request.urlopen(req2, timeout=10) as r:
        print('nginx_http', r.status)
        print('nginx_body', r.read().decode()[:200])
except Exception as e:
    print('nginx_err', type(e).__name__, getattr(e, 'code', ''), str(e)[:200])
    if hasattr(e, 'read'):
        try:
            print('nginx_err_body', e.read().decode()[:200])
        except Exception:
            pass

# snackhouse host
req3 = urllib.request.Request(
    'http://127.0.0.1/api/agency/login',
    data=body,
    headers={'Content-Type':'application/json','Host':'snackhouse-mechernich.de'},
    method='POST',
)
try:
    with urllib.request.urlopen(req3, timeout=10) as r:
        print('shy_http', r.status)
        print('shy_body', r.read().decode()[:200])
except Exception as e:
    print('shy_err', type(e).__name__, getattr(e, 'code', ''))
    if hasattr(e, 'read'):
        try:
            print('shy_err_body', e.read().decode()[:200])
        except Exception:
            pass

# nginx locations
import subprocess
print('--- nginx agency ---')
subprocess.run("grep -n 'agency\|api' /etc/nginx/sites-enabled/*digitale* /etc/nginx/sites-enabled/*snack* 2>/dev/null | head -60", shell=True)
"""

sftp = client.open_sftp()
with sftp.file("/tmp/test_agency_login.py", "w") as f:
    f.write(REMOTE)
sftp.close()
print(run("/root/app/venv/bin/python /tmp/test_agency_login.py"))
print("--- journal ---")
print(run("journalctl -u snack-api -n 30 --no-pager"))
client.close()
