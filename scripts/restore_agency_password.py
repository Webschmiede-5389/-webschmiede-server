"""Restore AGENCY_ADMIN_PASSWORD from agency-credentials.local.txt."""
import re
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import paramiko
from agency_config import ssh_connect

ROOT = os.path.dirname(os.path.dirname(__file__))
CRED = os.path.join(ROOT, "agency-credentials.local.txt")
ENV = "/root/app/backend/.env"
SECRETS = "/root/app/deploy.secrets.local"


def load_old_password() -> str:
    if not os.path.isfile(CRED):
        raise SystemExit(f"{CRED} nicht gefunden")
    for line in open(CRED, encoding="utf-8"):
        if line.strip().startswith("Passwort:"):
            return line.split(":", 1)[1].strip()
    raise SystemExit("Passwort: Zeile nicht in agency-credentials.local.txt")


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


def clean_secrets(text: str, pw: str) -> str:
    lines = text.splitlines()
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
        if cleaned and cleaned[-1].strip():
            cleaned.append("")
        cleaned.append(f"AGENCY_ADMIN_PASSWORD={pw}")
    return "\n".join(cleaned).rstrip() + "\n"


pw = load_old_password()
print("Stelle altes Agency-Passwort wieder her…")

client = paramiko.SSHClient()
ssh_connect(client)
sftp = client.open_sftp()

try:
    with sftp.open(SECRETS, "r") as f:
        secrets_text = f.read().decode("utf-8")
except FileNotFoundError:
    secrets_text = "# Webschmiede deploy.secrets.local\n"

with sftp.open(ENV, "r") as f:
    env_text = f.read().decode("utf-8")

with sftp.open(SECRETS, "w") as f:
    f.write(clean_secrets(secrets_text, pw))
with sftp.open(ENV, "w") as f:
    f.write(rewrite_env(env_text, "AGENCY_ADMIN_PASSWORD", pw))

sftp.close()
client.exec_command("systemctl restart snack-api")
time.sleep(2)

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
    print("login test:", getattr(e, "code", e))
"""
sftp = client.open_sftp()
with sftp.open("/tmp/test_agency_pw.py", "w") as f:
    f.write(test_py)
sftp.close()
_, out, _ = client.exec_command("/root/app/venv/bin/python /tmp/test_agency_pw.py")
print(out.read().decode().strip())
client.exec_command("rm -f /tmp/test_agency_pw.py")
client.close()
print("Fertig — Login wieder mit dem Passwort aus agency-credentials.local.txt")
