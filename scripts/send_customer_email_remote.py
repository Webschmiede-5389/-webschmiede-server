"""Send customer email via agency SMTP on the server."""
from __future__ import annotations

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import paramiko
from agency_config import ssh_connect

TO = "safer@ivk-global.de"
SUBJECT = "Meta-Werberechnungen automatisch an Ihre Buchhaltung"
BODY_FILE = os.path.join(ROOT, "scripts", "outbox", "safer-meta-buchhaltung.txt")

client = paramiko.SSHClient()
ssh_connect(client)

# BCC on server
client.exec_command(
    "grep -q '^AGENCY_MAIL_BCC=' /root/app/deploy.secrets.local 2>/dev/null || "
    "echo 'AGENCY_MAIL_BCC=christian.kummetat@gmail.com' >> /root/app/deploy.secrets.local"
)

sftp = client.open_sftp()
sftp.put(
    os.path.join(ROOT, "app", "backend", "agency_mail.py"),
    "/root/app/backend/agency_mail.py",
)
sftp.put(
    os.path.join(ROOT, "scripts", "send_customer_email.py"),
    "/root/app/scripts/send_customer_email.py",
)
sftp.put(BODY_FILE, "/tmp/safer-mail.txt")
sftp.close()

cmd = (
    "/root/app/venv/bin/python /root/app/scripts/send_customer_email.py "
    f'--to {TO!r} --subject {SUBJECT!r} --body-file /tmp/safer-mail.txt'
)
_, out, err = client.exec_command(cmd, timeout=90)
time.sleep(2)
stdout = out.read().decode()
stderr = err.read().decode()
print(stdout or stderr)
client.exec_command("rm -f /tmp/safer-mail.txt")
client.close()

if "Gesendet" not in stdout:
    raise SystemExit(1)
