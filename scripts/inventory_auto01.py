#!/usr/bin/env python3
"""Inventory auto-01 before migration."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agency_config import ssh_connect
import paramiko

cmds = [
    "hostname; uname -a; df -h / | tail -1",
    "systemctl is-active n8n 2>/dev/null; systemctl is-active snack-api 2>/dev/null || true",
    "ls -la /opt/n8n 2>/dev/null | head -15",
    "du -sh /opt/n8n /root/app 2>/dev/null",
    "crontab -l 2>/dev/null || echo 'no crontab'",
    "ls /etc/systemd/system/*.service 2>/dev/null | xargs -n1 basename",
    "ss -tlnp | grep -E '5678|8000' || true",
    "ip -4 addr show | grep inet",
]

c = paramiko.SSHClient()
ssh_connect(c, role="auto")
for cmd in cmds:
    print("===", cmd[:60])
    _, o, e = c.exec_command(cmd, timeout=30)
    print(o.read().decode("utf-8", errors="replace"))
    err = e.read().decode().strip()
    if err:
        print("ERR:", err[:200])
c.close()
