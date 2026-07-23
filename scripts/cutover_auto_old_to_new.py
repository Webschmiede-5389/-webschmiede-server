#!/usr/bin/env python3
"""Stop automation on old auto-01; ensure new Auto-01neu is active."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import paramiko
from agency_config import ssh_connect, target_secrets, _read_file_secrets

OLD_HOST = os.environ.get("OLD_AUTO_HOST", "204.168.174.152")


def run(c: paramiko.SSHClient, cmd: str, timeout: int = 60) -> str:
    _, o, e = c.exec_command(cmd, timeout=timeout)
    o.channel.recv_exit_status()
    return (o.read() + e.read()).decode("utf-8", errors="replace").strip()


def connect_old() -> paramiko.SSHClient:
    secrets = _read_file_secrets()
    pw = os.environ.get("OLD_AUTO_PASSWORD") or secrets.get("OLD_AUTO_PASSWORD") or "AsfpkUuNNuit"
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(OLD_HOST, username="root", password=pw, timeout=25, look_for_keys=False, allow_agent=False)
    return c


def stop_old() -> None:
    print(f"Stoppe alt: {OLD_HOST}")
    c = connect_old()
    out = run(
        c,
        """
systemctl stop n8n 2>/dev/null || true
systemctl disable n8n 2>/dev/null || true
crontab -r 2>/dev/null || true
systemctl is-active n8n 2>/dev/null || echo inactive
crontab -l 2>/dev/null | wc -l || echo 0
""",
    )
    print(out)
    c.close()
    print("OK alt gestoppt (n8n + cron)")


def start_new() -> None:
    t = target_secrets("auto")
    print(f"Starte neu: {t['SERVER_HOST']}")
    c = paramiko.SSHClient()
    ssh_connect(c, role="auto")
    out = run(
        c,
        """
systemctl enable n8n 2>/dev/null || true
systemctl restart n8n
sleep 2
systemctl is-active n8n
crontab -l 2>/dev/null | wc -l
""",
    )
    print(out)
    c.close()
    print("OK neu aktiv")


def smoke() -> None:
    web = paramiko.SSHClient()
    ssh_connect(web, role="web")
    code = run(
        web,
        'curl -sk -o /dev/null -w "%{http_code}" -H "Host: digitalehandwerkskunst.de" https://127.0.0.1/n8n/',
    )
    web.close()
    print(f"n8n proxy: HTTP {code}")


def main() -> int:
    stop_old()
    start_new()
    smoke()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
