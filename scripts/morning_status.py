#!/usr/bin/env python3
"""Kurzer Morgen-Status (keine Secret-Werte ausgeben)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import paramiko
from agency_config import ssh_connect

c = paramiko.SSHClient()
ssh_connect(c, role="web")


def run(cmd: str) -> str:
    _, o, _ = c.exec_command(cmd, timeout=30)
    return o.read().decode("utf-8", errors="replace").strip()


print("Cal.com HTTP:", run('curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1/cal/'))
print(
    "Docker:",
    run("docker ps --format '{{.Names}} {{.Status}}' 2>/dev/null | head -5 || echo 'docker nicht aktiv'"),
)
# Nur Key-Namen, nie Werte
print(
    "Env keys:",
    run(
        "grep -E '^(AGENCY_ADMIN|CALCOM|N8N_SEMINAR)' /root/app/backend/.env 2>/dev/null "
        "| cut -d= -f1 || echo 'keine vars'"
    ),
)
c.close()
