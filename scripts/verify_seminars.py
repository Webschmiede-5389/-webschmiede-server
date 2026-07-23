#!/usr/bin/env python3
"""Verify seminar pages, API and agency auth on server."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import paramiko
from agency_config import load_secrets, ssh_connect, SECRETS_FILE

HOST = load_secrets()["SERVER_HOST"]


def load_agency_pw() -> str:
    cred = os.path.join(os.path.dirname(os.path.dirname(__file__)), "agency-credentials.local.txt")
    if os.path.isfile(cred):
        for line in open(cred, encoding="utf-8"):
            if line.startswith("Passwort:"):
                return line.split(":", 1)[1].strip()
    if SECRETS_FILE.exists():
        for line in SECRETS_FILE.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("AGENCY_ADMIN_PASSWORD="):
                return line.split("=", 1)[1].strip()
    return ""


def run(client, cmd, timeout=30):
    _, out, err = client.exec_command(cmd, timeout=timeout)
    return out.read().decode("utf-8", errors="replace").strip()


def main():
    client = paramiko.SSHClient()
    ssh_connect(client)
    pw = load_agency_pw()

    checks = [
        ("GET /seminare", f'curl -s -o /dev/null -w "%{{http_code}}" http://127.0.0.1/seminare'),
        ("GET /agency", f'curl -s -o /dev/null -w "%{{http_code}}" http://127.0.0.1/agency'),
        ("API /api/seminars", 'curl -s http://127.0.0.1:8000/api/seminars'),
        ("API ohne Auth", 'curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/agency/seminars'),
    ]
    print("=== Seminar-Verifikation ===\n")
    ok = True
    for name, cmd in checks:
        result = run(client, cmd)
        print(f"{name}: {result[:120]}")
        if name.endswith("ohne Auth") and result != "401":
            ok = False
            print("  WARN: erwartet 401")
        elif name.startswith("GET") and result != "200":
            ok = False

    if pw:
        auth_cmd = (
            f'curl -s -o /dev/null -w "%{{http_code}}" '
            f'-H "X-Agency-Password: {pw}" http://127.0.0.1:8000/api/agency/seminars'
        )
        code = run(client, auth_cmd)
        print(f"API mit Auth: {code}")
        if code != "200":
            ok = False
    else:
        print("API mit Auth: SKIP (kein Passwort lokal)")

    api_json = run(client, "curl -s http://127.0.0.1:8000/api/seminars")
    try:
        data = json.loads(api_json)
        n = len(data.get("seminars", []))
        print(f"\nSeminare in DB: {n}")
        if n == 0:
            ok = False
    except json.JSONDecodeError:
        ok = False

    client.close()
    print("\n" + ("OK" if ok else "FEHLER — Details pruefen"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
