#!/usr/bin/env python3
"""Disable Hetzner capacity buyer cron (targets already done)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paramiko
from agency_config import ssh_connect


def main():
    c = paramiko.SSHClient()
    ssh_connect(c, role="auto")
    cmd = (
        "crontab -l 2>/dev/null | grep -v hetzner_buyer_cron | crontab - ; "
        "echo 'remaining:'; crontab -l 2>/dev/null | grep -i hetzner || echo 'hetzner buyer cron removed'"
    )
    _, o, e = c.exec_command(cmd, timeout=30)
    print((o.read() + e.read()).decode("utf-8", "replace"))
    c.close()


if __name__ == "__main__":
    main()
