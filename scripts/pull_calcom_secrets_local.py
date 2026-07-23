#!/usr/bin/env python3
"""Pull CALCOM_* from server secrets into local deploy.secrets.local (no stdout of secrets)."""
import os
import sys

import paramiko

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency_config import ssh_connect

client = paramiko.SSHClient()
ssh_connect(client, timeout=45, banner_timeout=45, role="web")
_, out, _ = client.exec_command(
    "grep -E '^CALCOM_(URL|API_KEY)=' /root/app/deploy.secrets.local"
)
lines = out.read().decode("utf-8", "replace").strip().splitlines()
client.close()

local = os.path.join(ROOT, "deploy.secrets.local")
text = open(local, encoding="utf-8").read() if os.path.isfile(local) else ""
changed = False
for line in lines:
    if "=" not in line:
        continue
    k = line.split("=", 1)[0].strip()
    if f"{k}=" in text:
        # replace existing
        import re
        text2, n = re.subn(rf"(?m)^{k}=.*$", line, text)
        if n:
            text = text2
            changed = True
    else:
        text = text.rstrip() + "\n" + line + "\n"
        changed = True
if changed:
    open(local, "w", encoding="utf-8").write(text if text.endswith("\n") else text + "\n")
    print("LOCAL_SECRETS_UPDATED", len(lines), "keys")
else:
    print("LOCAL_SECRETS_UNCHANGED")
