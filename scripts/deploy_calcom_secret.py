#!/usr/bin/env python3
"""Deploy Cal.com secrets fields + restart API."""
import os
import sys

import paramiko

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency_config import ssh_connect

client = paramiko.SSHClient()
ssh_connect(client, timeout=60, banner_timeout=60, role="web")
sftp = client.open_sftp()
for loc, rem in [
    ("app/backend/agency_secrets.py", "/root/app/backend/agency_secrets.py"),
    ("app/backend/main.py", "/root/app/backend/main.py"),
]:
    sftp.put(os.path.join(ROOT, loc.replace("/", os.sep)), rem)
    print("put", loc)
sftp.close()


def run(cmd: str) -> None:
    _, out, err = client.exec_command(cmd, timeout=90)
    text = (out.read() + err.read()).decode("utf-8", "replace").strip()
    if text:
        print(text)


run("systemctl restart snack-api")
run("sleep 1; systemctl is-active snack-api")
run(
    "/root/app/venv/bin/python -c \"import agency_secrets as s; "
    "print('has_calcom_key', any(i['key']=='CALCOM_API_KEY' for i in s.KEY_CATALOG)); "
    "print('sync', 'CALCOM_API_KEY' in s.ENV_SYNC_KEYS)\""
)
client.close()
print("OK")
