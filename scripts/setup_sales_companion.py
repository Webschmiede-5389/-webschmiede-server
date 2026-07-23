#!/usr/bin/env python3
"""Sales-Companion Cron auf web: alle 4 Stunden Reminders + Digest."""
from __future__ import annotations

import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agency_config import ssh_connect


def lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def main() -> int:
    c = paramiko.SSHClient()
    ssh_connect(c, role="web")
    sftp = c.open_sftp()
    for local, remote, shell in [
        (ROOT / "app/backend/sales_companion.py", "/root/app/backend/sales_companion.py", False),
        (ROOT / "app/backend/sales_pipeline.py", "/root/app/backend/sales_pipeline.py", False),
        (ROOT / "app/backend/buchhaltung_onboarding.py", "/root/app/backend/buchhaltung_onboarding.py", False),
        (ROOT / "scripts/sales_companion.sh", "/root/app/scripts/sales_companion.sh", True),
    ]:
        data = lf(local.read_bytes()) if shell else local.read_bytes().replace(b"\r\n", b"\n")
        with sftp.file(remote, "wb") as f:
            f.write(data)
        if shell:
            c.exec_command(f"chmod +x {remote}", timeout=10)
        print("put", remote)
    cron = "15 */4 * * * /root/app/scripts/sales_companion.sh"
    _, o, e = c.exec_command(
        "(crontab -l 2>/dev/null | grep -v sales_companion.sh; echo '%s') | crontab -" % cron,
        timeout=30,
    )
    o.channel.recv_exit_status()
    _, o2, _ = c.exec_command("crontab -l | grep sales_companion || true", timeout=15)
    print("cron:", o2.read().decode().strip())
    _, o3, e3 = c.exec_command("systemctl restart snack-api && sleep 1 && systemctl is-active snack-api", timeout=30)
    print((o3.read() + e3.read()).decode())
    sftp.close()
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
