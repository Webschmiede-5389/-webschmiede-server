#!/usr/bin/env python3
"""Diagnose Agency-Login / Reset (ohne Secrets auszugeben)."""
import os
import sys

import paramiko

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency_config import ssh_connect

SCRIPT = r"""
import os, sqlite3, json
from pathlib import Path

# Find DB
cands = [
  '/root/app/backend/orders.db',
  '/root/app/orders.db',
  '/var/www/snackhouse-mechernich/../',
]
db = None
for p in ['/root/app/backend/orders.db', '/root/app/data/orders.db', '/root/app/orders.db']:
  if os.path.isfile(p):
    db = p
    break
# also search
if not db:
  for root, dirs, files in os.walk('/root/app'):
    if 'orders.db' in files:
      db = os.path.join(root, 'orders.db')
      break
    if 'portal' in ''.join(files).lower():
      pass
print('DB', db or 'NONE')

smtp_keys = ['AGENCY_SMTP_HOST','AGENCY_SMTP_USER','AGENCY_SMTP_PASS','AGENCY_OWNER_EMAIL','AGENCY_BOOTSTRAP_USER','PUBLIC_BASE_URL']
# from process env via systemd? read secrets file
sec = Path('/root/app/deploy.secrets.local')
envp = Path('/root/app/backend/.env')
vals = {}
for path in (sec, envp):
  if path.exists():
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
      if '=' in line and not line.strip().startswith('#'):
        k,v = line.split('=',1)
        vals[k.strip()] = v.strip()
print('SECRETS_FILE', sec.exists(), 'ENV_FILE', envp.exists())
print('AGENCY_ADMIN_PASSWORD_SET', bool(vals.get('AGENCY_ADMIN_PASSWORD')))
print('AGENCY_BOOTSTRAP_USER', vals.get('AGENCY_BOOTSTRAP_USER') or '(default christian)')
print('AGENCY_OWNER_EMAIL_SET', bool(vals.get('AGENCY_OWNER_EMAIL')))
print('SMTP_HOST_SET', bool(vals.get('AGENCY_SMTP_HOST')))
print('SMTP_USER_SET', bool(vals.get('AGENCY_SMTP_USER')))
print('SMTP_PASS_SET', bool(vals.get('AGENCY_SMTP_PASS')))
print('PUBLIC_BASE_URL', vals.get('PUBLIC_BASE_URL') or '(empty)')

if db:
  con = sqlite3.connect(db)
  con.row_factory = sqlite3.Row
  try:
    rows = con.execute("SELECT id, username, email, role, totp_enabled, length(password_hash) as phlen, reset_token_hash IS NOT NULL as has_reset, reset_expires FROM portal_users").fetchall()
    print('USERS', len(rows))
    for r in rows:
      print('USER', dict(r))
  except Exception as e:
    print('USER_QUERY_ERR', type(e).__name__, str(e)[:120])
  # list tables
  tabs = [t[0] for t in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
  print('TABLES', ','.join(tabs)[:300])
"""

client = paramiko.SSHClient()
ssh_connect(client, timeout=45, banner_timeout=45, role="web")
sftp = client.open_sftp()
remote = "/tmp/diag_agency_auth.py"
with sftp.file(remote, "w") as f:
    f.write(SCRIPT)
sftp.close()
_, out, err = client.exec_command(f"python3 {remote}", timeout=30)
print((out.read() + err.read()).decode("utf-8", "replace"))
client.close()
