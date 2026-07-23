#!/usr/bin/env python3
"""Smoke: /nils Seite + API auf digitalehandwerkskunst.de."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agency_config import ssh_connect
import paramiko

REMOTE = "/tmp/smoke_nils.py"
REMOTE_SCRIPT = r'''
import json
import os
import urllib.error
import urllib.request

pw = os.environ.get("SMOKE_AGENCY_PW", "")

def get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, r.read(6000).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(600).decode("utf-8", errors="replace")

checks = []
host = {"Host": "digitalehandwerkskunst.de"}
for path in ("/nils", "/nils.html"):
    code, body = get(f"http://127.0.0.1{path}", host)
    ok = code == 200 and "Nils" in body and "Ops" in body
    checks.append([f"page{path}", ok, f"HTTP {code} title={'Nils' in body}"])

if pw:
    code, body = get("http://127.0.0.1:8000/api/nils/history", {"X-Agency-Password": pw})
    checks.append(["api_history", code == 200, f"HTTP {code}"])
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/nils/message",
        data=json.dumps({"message": "Hilfe"}).encode("utf-8"),
        headers={"X-Agency-Password": pw, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
    checks.append(["api_message", code == 200, f"HTTP {code}"])
else:
    checks.append(["api_history", False, "no password"])

print(json.dumps(checks))
'''


def load_password(client: paramiko.SSHClient) -> str:
    _, out, _ = client.exec_command(
        "grep '^AGENCY_ADMIN_PASSWORD=' /root/app/deploy.secrets.local 2>/dev/null | head -1 | cut -d= -f2-"
    )
    return out.read().decode("utf-8", errors="replace").strip()


def main() -> int:
    client = paramiko.SSHClient()
    ssh_connect(client, role="web")
    # ensure nils.html in webroot used by nginx
    client.exec_command(
        "cp /root/app/static/nils.html /var/www/snackhouse-mechernich/nils.html 2>/dev/null; "
        "cp /root/app/static/nils.html /var/www/digitalehandwerkskunst/nils.html 2>/dev/null; "
        "ls -la /var/www/snackhouse-mechernich/nils.html /var/www/digitalehandwerkskunst/nils.html 2>&1"
    )
    import time
    time.sleep(1)
    pw = load_password(client)
    sftp = client.open_sftp()
    with sftp.file(REMOTE, "w") as f:
        f.write(REMOTE_SCRIPT)
    sftp.close()
    _, out, err = client.exec_command(f"SMOKE_AGENCY_PW={pw!r} /root/app/venv/bin/python3 {REMOTE}", timeout=60)
    raw = out.read().decode().strip()
    client.exec_command(f"rm -f {REMOTE}")
    client.close()
    if not raw:
        print("FAIL:", err.read().decode())
        return 1
    failed = 0
    for name, ok, detail in json.loads(raw):
        print(f"  [{'OK' if ok else 'FAIL'}] {name}: {detail}")
        if not ok:
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
