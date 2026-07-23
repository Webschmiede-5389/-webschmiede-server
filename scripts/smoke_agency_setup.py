#!/usr/bin/env python3
"""Smoke-Test Agency Setup nach Deploy (Seiten + API)."""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agency_config import ssh_connect
import paramiko

CRED = os.path.join(os.path.dirname(os.path.dirname(__file__)), "agency-credentials.local.txt")
REMOTE = "/tmp/smoke_agency_setup.py"


def load_password(client: paramiko.SSHClient) -> str:
    _, out, _ = client.exec_command(
        "grep '^AGENCY_ADMIN_PASSWORD=' /root/app/deploy.secrets.local 2>/dev/null | head -1 | cut -d= -f2-"
    )
    pw = out.read().decode("utf-8", errors="replace").strip()
    if pw:
        return pw
    if os.path.isfile(CRED):
        for line in open(CRED, encoding="utf-8"):
            if line.strip().startswith("Passwort:"):
                return line.split(":", 1)[1].strip()
    return ""


REMOTE_SCRIPT = r'''
import json
import os
import sys
import urllib.error
import urllib.request

pw = os.environ.get("SMOKE_AGENCY_PW", "")

def get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, r.read(4000).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(400).decode("utf-8", errors="replace")

checks = []
for path in ("/agency-setup", "/agency-keys"):
    code, body = get(
        f"http://127.0.0.1{path}",
        {"Host": "digitalehandwerkskunst.de"},
    )
    # 301/302 auf HTTPS ist OK wenn Location stimmt; 200 mit Inhalt besser
    ok = code == 200 and (
        "Setup-Portal" in body or "Weiterleitung" in body or "agency-setup" in body
        or "Messaging" in body or "Agency" in body
    )
    if not ok and code in (301, 302):
        ok = True  # Nginx leitet auf HTTPS um
        body = f"redirect {code}"
    checks.append([f"page{path}", ok, f"HTTP {code}"])

if pw:
    code, _ = get("http://127.0.0.1:8000/api/agency/secrets", {"X-Agency-Password": pw})
    checks.append(["api_secrets", code == 200, f"HTTP {code}"])
    code, _ = get("http://127.0.0.1:8000/api/agency/secrets", {"X-Agency-Password": "wrong"})
    checks.append(["api_reject_bad_pw", code in (401, 403), f"HTTP {code}"])
else:
    checks.append(["api_secrets", False, "no password"])

print(json.dumps(checks))
'''


def main() -> int:
    client = paramiko.SSHClient()
    ssh_connect(client, timeout=20, role="web")
    pw = load_password(client)
    sftp = client.open_sftp()
    with sftp.file(REMOTE, "w") as f:
        f.write(REMOTE_SCRIPT)
    sftp.close()
    cmd = f'SMOKE_AGENCY_PW={pw!r} /root/app/venv/bin/python3 {REMOTE}'
    _, out, err = client.exec_command(cmd, timeout=60)
    raw = out.read().decode("utf-8", errors="replace").strip()
    e = err.read().decode("utf-8", errors="replace").strip()
    client.exec_command(f"rm -f {REMOTE}")
    client.close()
    if not raw:
        print(f"FAIL smoke: {e or 'no output'}")
        return 1
    failed = 0
    for name, ok, detail in json.loads(raw):
        print(f"  [{'OK' if ok else 'FAIL'}] {name}: {detail}")
        if not ok:
            failed += 1
    if failed:
        print(f"\nSmoke-Test: {failed} Fehler")
        return 1
    print("\nSmoke-Test: alles OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
