"""Inspect and fix AGENCY_ADMIN_PASSWORD sync (handles special chars)."""
import re
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import paramiko
from agency_config import ssh_connect

ENV = "/root/app/backend/.env"
SECRETS = "/root/app/deploy.secrets.local"


def parse_keys(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def rewrite_env(text: str, key: str, value: str) -> str:
    lines = text.splitlines()
    found = False
    out = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            if not found:
                out.append(f"{key}={value}")
                found = True
            continue
        out.append(line.rstrip())
    if not found:
        out.append(f"{key}={value}")
    return "\n".join(out).rstrip() + "\n"


client = paramiko.SSHClient()
ssh_connect(client)
sftp = client.open_sftp()

with sftp.open(SECRETS, "r") as f:
    secrets_text = f.read().decode("utf-8")
with sftp.open(ENV, "r") as f:
    env_text = f.read().decode("utf-8")

secrets_keys = parse_keys(secrets_text)
env_keys = parse_keys(env_text)

matches = re.findall(r"^AGENCY_ADMIN_PASSWORD=.*$", secrets_text, re.M)
print(f"deploy.secrets.local: {len(matches)} Eintrag(e)")
if len(matches) > 1:
    print("  -> Duplikat wird bereinigt (letzter Eintrag zählt)")

pw = secrets_keys.get("AGENCY_ADMIN_PASSWORD", "")
if not pw:
    print("FEHLER: Kein AGENCY_ADMIN_PASSWORD in deploy.secrets.local")
    sftp.close()
    client.close()
    raise SystemExit(1)

env_pw = env_keys.get("AGENCY_ADMIN_PASSWORD", "")
if env_pw == pw:
    print("OK — .env bereits synchron")
else:
    print("Sync — schreibe .env neu")
    new_env = rewrite_env(env_text, "AGENCY_ADMIN_PASSWORD", pw)
    with sftp.open(ENV, "w") as f:
        f.write(new_env)

if len(matches) > 1:
    # Keep single canonical line at end of secrets file
    lines = secrets_text.splitlines()
    cleaned = []
    seen = False
    for line in lines:
        if line.strip().startswith("AGENCY_ADMIN_PASSWORD="):
            if not seen:
                cleaned.append(f"AGENCY_ADMIN_PASSWORD={pw}")
                seen = True
            continue
        cleaned.append(line.rstrip())
    if not seen:
        cleaned.append(f"AGENCY_ADMIN_PASSWORD={pw}")
    with sftp.open(SECRETS, "w") as f:
        f.write("\n".join(cleaned).rstrip() + "\n")
    print("deploy.secrets.local bereinigt")

sftp.close()

_, out, _ = client.exec_command("systemctl restart snack-api")
out.read()
time.sleep(2)

# Test via Python on server (no shell escaping issues)
test_py = f"""
import urllib.request
req = urllib.request.Request(
    "http://127.0.0.1:8000/api/agency/secrets",
    headers={{"X-Agency-Password": {pw!r}}},
)
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        print("login test:", r.status)
except Exception as e:
    if hasattr(e, "code"):
        print("login test:", e.code)
    else:
        print("login test: error", e)
"""
sftp = client.open_sftp()
with sftp.open("/tmp/test_agency_pw.py", "w") as f:
    f.write(test_py)
sftp.close()
_, out, err = client.exec_command("/root/app/venv/bin/python /tmp/test_agency_pw.py")
print(out.read().decode().strip())
e = err.read().decode().strip()
if e:
    print("ERR:", e[:200])

client.exec_command("rm -f /tmp/test_agency_pw.py")
client.close()
print("Fertig.")
