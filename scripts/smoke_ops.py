#!/usr/bin/env python3
"""Smoke-Test Agency Ops API."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agency_config import ssh_connect
import paramiko


def load_password(client):
    _, out, _ = client.exec_command(
        "grep '^AGENCY_ADMIN_PASSWORD=' /root/app/deploy.secrets.local 2>/dev/null | head -1 | cut -d= -f2-"
    )
    return out.read().decode("utf-8", errors="replace").strip()


def main():
    client = paramiko.SSHClient()
    ssh_connect(client, role="web")
    pw = load_password(client)
    if not pw:
        print("FAIL: kein Agency-Passwort")
        return 1
    cmd = (
        f"curl -s -H 'X-Agency-Password: {pw}' http://127.0.0.1:8000/api/agency/ops/overview"
    )
    _, out, err = client.exec_command(cmd, timeout=30)
    body = out.read().decode("utf-8", errors="replace")
    if not body.strip().startswith("{"):
        print("FAIL: keine JSON-Antwort", body[:200])
        return 1
    data = json.loads(body)
    if "server" not in data or "kpis" not in data:
        print("FAIL: unvollständige Antwort", list(data.keys()))
        return 1
    print("OK ops/overview:", data.get("kunde_count"), "Kunden, server ok=", data.get("server", {}).get("ok"))
    backup = data.get("server", {}).get("backup", {})
    off = backup.get("offsite", {})
    print("Backup lokal:", backup.get("ok"), backup.get("detail", "")[:60])
    print("Backup offsite:", off.get("ok"), off.get("detail", "")[:60])
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
