"""Verify agency SMTP secrets on server (masked, optional test)."""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import paramiko
from agency_config import ssh_connect

SECRETS = "/root/app/deploy.secrets.local"
CRED = os.path.join(os.path.dirname(os.path.dirname(__file__)), "agency-credentials.local.txt")

SMTP_KEYS = [
    "AGENCY_SMTP_HOST",
    "AGENCY_SMTP_PORT",
    "AGENCY_SMTP_USER",
    "AGENCY_SMTP_PASS",
    "AGENCY_SMTP_FROM",
    "AGENCY_REPLY_TO",
    "AGENCY_OWNER_EMAIL",
]


def mask(key: str, val: str) -> str:
    if not val:
        return "(leer)"
    if key.endswith("_PASS"):
        return f"**** ({len(val)} Zeichen)"
    if "@" in val:
        parts = val.split("@", 1)
        return f"{parts[0][:2]}…@{parts[1]}"
    return val if len(val) <= 40 else val[:20] + "…"


def load_agency_pw() -> str:
    for line in open(CRED, encoding="utf-8"):
        if line.strip().startswith("Passwort:"):
            return line.split(":", 1)[1].strip()
    raise SystemExit("Agency-Passwort nicht in agency-credentials.local.txt")


client = paramiko.SSHClient()
ssh_connect(client)
sftp = client.open_sftp()

with sftp.open(SECRETS, "r") as f:
    text = f.read().decode("utf-8")

vals = {}
dupes = []
seen = set()
for line in text.splitlines():
    s = line.strip()
    if not s or s.startswith("#") or "=" not in s:
        continue
    k, v = line.split("=", 1)
    k, v = k.strip(), v.strip()
    if k in seen:
        dupes.append(k)
    seen.add(k)
    vals[k] = v

print("=== E-Mail-Daten (deploy.secrets.local) ===\n")
missing = []
for key in SMTP_KEYS:
    v = vals.get(key, "")
    status = "OK" if v else "FEHLT"
    if not v:
        missing.append(key)
    print(f"  [{status:5}] {key}")
    print(f"          {mask(key, v)}")

if dupes:
    print(f"\n  Warnung: doppelte Keys: {', '.join(sorted(set(dupes)))}")

required = ["AGENCY_SMTP_HOST", "AGENCY_SMTP_USER", "AGENCY_SMTP_PASS"]
complete = all(vals.get(k) for k in required)
print(f"\nSMTP vollständig: {'Ja' if complete else 'Nein — Host, User und Passwort nötig'}")

if complete:
    pw = load_agency_pw()
    test_py = f"""
import json, urllib.request
req = urllib.request.Request(
    "http://127.0.0.1:8000/api/agency/secrets/test/smtp",
    data=b"{{}}",
    headers={{
        "Content-Type": "application/json",
        "X-Agency-Password": {pw!r},
    }},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=45) as r:
        print(json.dumps(json.loads(r.read().decode()), ensure_ascii=False))
except Exception as e:
    body = e.read().decode() if hasattr(e, "read") else str(e)
    print(json.dumps({{"ok": False, "error": body or str(e)}}))
"""
    sftp = client.open_sftp()
    with sftp.open("/tmp/test_smtp.py", "w") as f:
        f.write(test_py)
    sftp.close()
    print("\n=== SMTP-Test (Test-Mail senden) ===\n")
    _, out, err = client.exec_command("/root/app/venv/bin/python /tmp/test_smtp.py", timeout=60)
    time.sleep(1)
    result = out.read().decode().strip()
    print(f"  {result}")
    client.exec_command("rm -f /tmp/test_smtp.py")
else:
    print("\nKein SMTP-Test — zuerst E-Mail-Felder im Setup-Portal ausfüllen.")

sftp.close()
client.close()
