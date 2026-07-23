#!/usr/bin/env python3
"""Ops-Guardian Cron auf web-01 installieren (alle 15 Min)."""
from __future__ import annotations

import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agency_config import ssh_connect  # noqa: E402


def normalize_lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def main() -> int:
    c = paramiko.SSHClient()
    ssh_connect(c, role="web")
    sftp = c.open_sftp()
    files = [
        (ROOT / "app/backend/ops_guardian.py", "/root/app/backend/ops_guardian.py", False),
        (ROOT / "app/backend/agency_shipcheck.py", "/root/app/backend/agency_shipcheck.py", False),
        (ROOT / "scripts/ops_guardian_cli.py", "/root/app/scripts/ops_guardian_cli.py", False),
        (ROOT / "scripts/ops_guardian.sh", "/root/app/scripts/ops_guardian.sh", True),
    ]
    for local, remote, shell in files:
        data = local.read_bytes()
        data = normalize_lf(data) if shell else data.replace(b"\r\n", b"\n")
        with sftp.file(remote, "wb") as f:
            f.write(data)
        if shell:
            c.exec_command(f"chmod +x {remote}", timeout=10)
        print("put", remote)

    cron_line = "*/15 * * * * /root/app/scripts/ops_guardian.sh"
    _, o, e = c.exec_command(
        "(crontab -l 2>/dev/null | grep -v ops_guardian.sh; echo '%s') | crontab -" % cron_line,
        timeout=30,
    )
    o.channel.recv_exit_status()
    print((o.read() + e.read()).decode("utf-8", "replace")[-400:])
    _, o2, _ = c.exec_command("crontab -l | grep ops_guardian || true", timeout=15)
    print("cron:", o2.read().decode().strip())
    _, o3, e3 = c.exec_command(
        "mkdir -p /var/lib/webschmiede /var/log; "
        "cd /root/app && PYTHONPATH=/root/app/backend /root/app/venv/bin/python "
        "/root/app/scripts/ops_guardian_cli.py run --no-repair 2>&1 | tail -50",
        timeout=120,
    )
    print((o3.read() + e3.read()).decode("utf-8", "replace")[-2500:])
    sftp.close()
    c.close()
    print("Ops-Guardian Cron installiert (*/15).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
