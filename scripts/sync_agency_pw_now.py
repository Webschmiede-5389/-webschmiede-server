#!/usr/bin/env python3
import os
import sys

import paramiko

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency_config import ssh_connect

REMOTE = r"""
from pathlib import Path
import sqlite3
from werkzeug.security import generate_password_hash

vals = {}
for p in (Path("/root/app/deploy.secrets.local"), Path("/root/app/backend/.env")):
    if not p.exists():
        continue
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip()
pw = (vals.get("AGENCY_ADMIN_PASSWORD") or "").strip()
assert len(pw) >= 10, "password too short"
con = sqlite3.connect("/root/app/backend/orders.db")
row = con.execute("SELECT id, username, email FROM portal_users WHERE role='agency' ORDER BY id LIMIT 1").fetchone()
assert row, "no agency user"
email = (row[2] or vals.get("AGENCY_OWNER_EMAIL") or "info@digitalehandwerkskunst.de").strip()
con.execute(
    "UPDATE portal_users SET password_hash=?, email=?, reset_token_hash=NULL, reset_expires=NULL WHERE id=?",
    (generate_password_hash(pw), email, row[0]),
)
con.commit()
print("SYNCED", row[1], "email=", email, "pw_len=", len(pw))
"""

client = paramiko.SSHClient()
ssh_connect(client, timeout=45, banner_timeout=45, role="web")
sftp = client.open_sftp()
sftp.put(os.path.join(ROOT, "app", "static", "agency.html"), "/root/app/static/agency.html")
with sftp.file("/tmp/sync_agency_pw.py", "w") as f:
    f.write(REMOTE)
sftp.close()


def run(cmd: str) -> None:
    _, out, err = client.exec_command(cmd, timeout=90)
    text = (out.read() + err.read()).decode("utf-8", "replace").strip()
    if text:
        print(text)


run("cp /root/app/static/agency.html /var/www/snackhouse-mechernich/agency.html")
run("cp /root/app/static/agency.html /var/www/digitalehandwerkskunst/agency.html")
run("/root/app/venv/bin/python /tmp/sync_agency_pw.py")
run("grep AGENCY_PUBLIC_BASE_URL /root/app/backend/.env || true")
run("systemctl restart snack-api")
run("sleep 1; systemctl is-active snack-api")
client.close()
print("OK")
