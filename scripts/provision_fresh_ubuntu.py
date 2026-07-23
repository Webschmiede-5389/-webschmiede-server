#!/usr/bin/env python3
"""Ubuntu-Basis nach Rebuild: Updates, Tools, Hostname."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import paramiko
from agency_config import _read_file_secrets, SECRETS_FILE

IP = sys.argv[1] if len(sys.argv) > 1 else "167.233.150.230"
HOSTNAME = sys.argv[2] if len(sys.argv) > 2 else "cx43-de-2-nbg1"
SECRETS_KEY_HOST = os.environ.get("SECRETS_KEY_HOST", "CX43_HOST")
SECRETS_KEY_PW = os.environ.get("SECRETS_KEY_PW", "CX43_PASSWORD")


def connect() -> paramiko.SSHClient:
    secrets = _read_file_secrets()
    pw = os.environ.get("SERVER_PASSWORD") or secrets.get(SECRETS_KEY_PW) or secrets.get("AUTO_PASSWORD", "")
    if not pw:
        raise SystemExit("Passwort fehlt (deploy.secrets.local oder SERVER_PASSWORD env)")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(IP, username="root", password=pw, timeout=30, look_for_keys=False, allow_agent=False)
    return c


def run(c: paramiko.SSHClient, cmd: str, timeout: int = 600) -> str:
    _, o, e = c.exec_command(cmd, timeout=timeout)
    o.channel.recv_exit_status()
    return (o.read() + e.read()).decode("utf-8", errors="replace").strip()


def update_secrets(pw: str) -> None:
    if not SECRETS_FILE.exists():
        return
    lines = []
    keys = {SECRETS_KEY_HOST: IP, SECRETS_KEY_PW: pw}
    seen = set()
    for line in SECRETS_FILE.read_text(encoding="utf-8").splitlines():
        k = line.split("=", 1)[0] if "=" in line else ""
        if k in keys:
            lines.append(f"{k}={keys[k]}")
            seen.add(k)
        else:
            lines.append(line)
    for k, v in keys.items():
        if k not in seen:
            lines.append(f"{k}={v}")
    SECRETS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    import time
    time.sleep(75)
    secrets = _read_file_secrets()
    pw = os.environ.get("SERVER_PASSWORD") or secrets.get(SECRETS_KEY_PW) or secrets.get("AUTO_PASSWORD", "")

    # Retry connect
    c = None
    for i in range(20):
        try:
            c = connect()
            break
        except Exception:
            time.sleep(15)
    if not c:
        print("SSH nach Rebuild nicht erreichbar")
        return 1

    hn = run(c, "hostname").splitlines()[0] if run(c, "hostname") else ""
    if hn == "rescue":
        c.close()
        print("FEHLER: noch Rescue-Modus")
        return 1

    print(f"Verbunden: {run(c, 'hostname')} | {run(c, 'head -2 /etc/os-release')}")

    run(c, f"""
export DEBIAN_FRONTEND=noninteractive
hostnamectl set-hostname {HOSTNAME}
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq python3 python3-pip python3-venv git curl ca-certificates ufw fail2ban htop
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
chage -I -1 -m 0 -M 99999 -E -1 root 2>/dev/null || true
""", timeout=900)

    print(run(c, "hostname; python3 --version; ufw status | head -5"))
    c.close()

    update_secrets(pw)
    print(f"OK {IP} Ubuntu bereit · Secrets: {SECRETS_KEY_HOST}, {SECRETS_KEY_PW}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
