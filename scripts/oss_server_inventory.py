#!/usr/bin/env python3
"""Quick inventory of web/auto for OSS install decisions."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import paramiko
from agency_config import ssh_connect

CMD = r"""
hostname
echo '---RAM---'
free -h | head -2
echo '---DOCKER---'
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null | head -40 || echo no-docker
echo '---OPT---'
ls /opt 2>/dev/null
echo '---DISK---'
df -h / | tail -1
"""


def main() -> int:
    for role in ("web", "auto"):
        c = paramiko.SSHClient()
        try:
            ssh_connect(c, role=role)
            _, o, e = c.exec_command(CMD, timeout=60)
            print(f"==== {role} ====")
            print((o.read() + e.read()).decode("utf-8", "replace"))
            c.close()
        except Exception as ex:
            print(f"==== {role} ERR ====", ex)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
