#!/usr/bin/env python3
"""Reset root password on Hetzner Cloud server and disable forced expiry."""
from __future__ import annotations

import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import paramiko
import requests
from agency_config import _read_file_secrets, SECRETS_FILE

IP = sys.argv[1] if len(sys.argv) > 1 else "88.198.170.156"


def find_server(token: str, ip: str) -> dict:
    r = requests.get("https://api.hetzner.cloud/v1/servers", headers={"Authorization": f"Bearer {token}"}, timeout=30)
    r.raise_for_status()
    for s in r.json().get("servers") or []:
        pub = (s.get("public_net") or {}).get("ipv4") or {}
        if pub.get("ip") == ip:
            return s
    raise SystemExit(f"Server {ip} nicht gefunden")


def main() -> int:
    token = _read_file_secrets().get("HETZNER_API_TOKEN", "").strip()
    if not token:
        return 1
    s = find_server(token, IP)
    sid = s["id"]
    rb = requests.post(
        f"https://api.hetzner.cloud/v1/servers/{sid}/actions/reset_password",
        headers={"Authorization": f"Bearer {token}"},
        json={},
        timeout=60,
    )
    rb.raise_for_status()
    pw = (rb.json().get("root_password") or "").strip()
    if not pw:
        print("Kein Passwort in Antwort")
        return 1

    import time
    time.sleep(8)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(IP, username="root", password=pw, timeout=30, look_for_keys=False, allow_agent=False)
    for cmd in (
        "chage -d 0 root 2>/dev/null; chage -I -1 -m 0 -M 99999 -E -1 root 2>/dev/null; true",
        f"echo 'root:{pw}' | chpasswd",
    ):
        _, o, e = c.exec_command(cmd)
        o.channel.recv_exit_status()
    c.close()

    secrets_key = os.environ.get("SECRETS_PW_KEY", "AUTO_PASSWORD")

    if SECRETS_FILE.exists():
        lines = []
        for line in SECRETS_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{secrets_key}="):
                lines.append(f"{secrets_key}={pw}")
            else:
                lines.append(line)
        if not any(x.startswith(f"{secrets_key}=") for x in lines):
            lines.append(f"{secrets_key}={pw}")
        SECRETS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"OK Passwort gesetzt fuer {s.get('name')} ({IP})")
    print(f"{secrets_key} in deploy.secrets.local aktualisiert")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
