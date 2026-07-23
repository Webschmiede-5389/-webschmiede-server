#!/usr/bin/env python3
"""Ensure CALCOM_URL + CALCOM_API_KEY synced from deploy.secrets.local into backend/.env."""
import os
import sys

import paramiko

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency_config import ssh_connect

REMOTE = r'''
from pathlib import Path
import re

sec = Path("/root/app/deploy.secrets.local")
env = Path("/root/app/backend/.env")
vals = {}
for line in sec.read_text(encoding="utf-8", errors="replace").splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        vals[k.strip()] = v.strip()

key = (vals.get("CALCOM_API_KEY") or "").strip()
found_under = None
if not key:
    for k, v in vals.items():
        if re.match(r"cal_(?:live|test)_", v or ""):
            key = v.strip()
            found_under = k
            break
url = (vals.get("CALCOM_URL") or "https://cal.digitalehandwerkskunst.de").strip().rstrip("/")

if found_under:
    print("FOUND_UNDER", found_under)
    text = sec.read_text(encoding="utf-8", errors="replace")
    if "CALCOM_API_KEY=" not in text:
        text = text.rstrip() + f"\nCALCOM_API_KEY={key}\n"
        if "CALCOM_URL=" not in text:
            text = text.rstrip() + f"\nCALCOM_URL={url}\n"
        sec.write_text(text, encoding="utf-8")
        print("WROTE_SECRETS_CANONICAL")

lines = env.read_text(encoding="utf-8", errors="replace").splitlines() if env.exists() else []
out = []
for line in lines:
    if "=" in line and not line.strip().startswith("#"):
        k = line.split("=", 1)[0].strip()
        if k in ("CALCOM_URL", "CALCOM_API_KEY"):
            continue
    out.append(line)
out.append(f"CALCOM_URL={url}")
out.append(f"CALCOM_API_KEY={key}")
env.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
print("SYNCED url=", url, "key_len=", len(key), "key_prefix=", (key[:8] + "...") if key else "(empty)")
'''

client = paramiko.SSHClient()
ssh_connect(client, timeout=60, banner_timeout=60, role="web")
sftp = client.open_sftp()
with sftp.file("/tmp/sync_calcom_key.py", "w") as f:
    f.write(REMOTE)
sftp.close()


def run(cmd: str) -> None:
    _, out, err = client.exec_command(cmd, timeout=90)
    text = (out.read() + err.read()).decode("utf-8", "replace").strip()
    if text:
        print(text)


run("/root/app/venv/bin/python /tmp/sync_calcom_key.py")
run("systemctl restart snack-api")
run("sleep 1; systemctl is-active snack-api")
# probe cal homepage for links
run("curl -sL https://cal.digitalehandwerkskunst.de/ | tr '\\n' ' ' | grep -oE 'href=\"/[^\"]+\"' | head -20")
client.close()
print("OK")
