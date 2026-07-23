#!/usr/bin/env python3
"""Sync Agency-DB-Passwort mit AGENCY_ADMIN_PASSWORD aus Secrets + Auth-Dateien deployen."""
import os
import sys

import paramiko

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency_config import ssh_connect

REMOTE_SYNC = r'''
import os, sqlite3, sys
from pathlib import Path
from werkzeug.security import generate_password_hash

def load_vals():
    vals = {}
    for path in (Path('/root/app/deploy.secrets.local'), Path('/root/app/backend/.env')):
        if not path.exists():
            continue
        for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
            if '=' in line and not line.strip().startswith('#'):
                k, v = line.split('=', 1)
                vals[k.strip()] = v.strip()
    return vals

vals = load_vals()
pw = (vals.get('AGENCY_ADMIN_PASSWORD') or '').strip()
if not pw:
    print('NO_PASSWORD')
    sys.exit(2)
if len(pw) < 10:
    print('PASSWORD_TOO_SHORT')
    sys.exit(3)

db = '/root/app/backend/orders.db'
con = sqlite3.connect(db)
con.row_factory = sqlite3.Row
row = con.execute("SELECT id, username, email FROM portal_users WHERE role='agency' ORDER BY id LIMIT 1").fetchone()
if not row:
    print('NO_AGENCY_USER')
    sys.exit(4)
email = (row['email'] or vals.get('AGENCY_OWNER_EMAIL') or 'info@digitalehandwerkskunst.de').strip()
con.execute(
    "UPDATE portal_users SET password_hash=?, email=?, reset_token_hash=NULL, reset_expires=NULL WHERE id=?",
    (generate_password_hash(pw), email, row['id']),
)
con.commit()
print('SYNCED', row['username'], 'email=', email, 'pw_len=', len(pw))
'''

client = paramiko.SSHClient()
ssh_connect(client, timeout=45, banner_timeout=45, role="web")
sftp = client.open_sftp()

# Upload fixed code
for loc, rem in [
    ("app/backend/auth_users.py", "/root/app/backend/auth_users.py"),
    ("app/backend/main.py", "/root/app/backend/main.py"),
    ("app/static/agency-auth.js", "/root/app/static/agency-auth.js"),
    ("app/static/agency.html", "/root/app/static/agency.html"),
]:
    local = os.path.join(ROOT, loc.replace("/", os.sep))
    print("put", loc)
    sftp.put(local, rem)

with sftp.file("/tmp/sync_agency_pw.py", "w") as f:
    f.write(REMOTE_SYNC)
sftp.close()

def run(cmd: str) -> str:
    _, out, err = client.exec_command(cmd, timeout=90)
    text = (out.read() + err.read()).decode("utf-8", "replace").strip()
    if text:
        print(text)
    return text

run("python3 /tmp/sync_agency_pw.py")
run("cp /root/app/static/agency.html /var/www/snackhouse-mechernich/agency.html")
run("cp /root/app/static/agency-auth.js /var/www/snackhouse-mechernich/agency-auth.js")
run("cp /root/app/static/agency.html /var/www/digitalehandwerkskunst/agency.html 2>/dev/null || true")
run("cp /root/app/static/agency-auth.js /var/www/digitalehandwerkskunst/agency-auth.js 2>/dev/null || true")
# Ensure agency public URL for resets
run(
    "grep -q '^AGENCY_PUBLIC_BASE_URL=' /root/app/backend/.env "
    "&& sed -i 's|^AGENCY_PUBLIC_BASE_URL=.*|AGENCY_PUBLIC_BASE_URL=https://digitalehandwerkskunst.de|' /root/app/backend/.env "
    "|| echo 'AGENCY_PUBLIC_BASE_URL=https://digitalehandwerkskunst.de' >> /root/app/backend/.env"
)
run("systemctl restart snack-api")
run("systemctl is-active snack-api")
client.close()
print("OK")
