#!/usr/bin/env python3
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agency_config import ssh_connect
import paramiko

c = paramiko.SSHClient()
ssh_connect(c, role="web")
cmds = [
    "ls -la /etc/nginx/sites-enabled/digitalehandwerkskunst.de",
    "grep -n 'location = /nils\\|server_name\\|listen ' /etc/nginx/sites-available/digitalehandwerkskunst.de",
    "wc -l /etc/nginx/sites-available/digitalehandwerkskunst.de",
    "sed -n '90,200p' /etc/nginx/sites-available/digitalehandwerkskunst.de",
]
for cmd in cmds:
    print("===", cmd)
    _, o, _ = c.exec_command(cmd)
    print(o.read().decode("utf-8", errors="replace"))
c.close()
