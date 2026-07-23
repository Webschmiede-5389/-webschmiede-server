#!/usr/bin/env python3
import sys, os
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agency_config import ssh_connect
import paramiko

c = paramiko.SSHClient()
ssh_connect(c, role="web")
cmds = [
    "grep -c 'location = /nils' /etc/nginx/sites-available/digitalehandwerkskunst.de",
    "grep -c 'server_name digitalehandwerkskunst' /etc/nginx/sites-available/digitalehandwerkskunst.de",
    'curl -sk -H "Host: digitalehandwerkskunst.de" https://127.0.0.1/nils -o /tmp/nils.out -w "%{http_code}"; echo; head -5 /tmp/nils.out',
    'nginx -T 2>/dev/null | grep -A3 "location = /nils" | head -20',
]
for cmd in cmds:
    print("---", cmd[:70])
    _, o, _ = c.exec_command(cmd)
    print(o.read().decode("utf-8", errors="replace"))
c.close()
