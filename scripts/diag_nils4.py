#!/usr/bin/env python3
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agency_config import ssh_connect
import paramiko

c = paramiko.SSHClient()
ssh_connect(c, role="web")
for f in ("/etc/nginx/sites-enabled/digitalehandwerkskunst.de", "/etc/nginx/sites-available/digitalehandwerkskunst.de"):
    _, o, _ = c.exec_command(f"grep -c 'location = /nils' {f}; wc -c {f}")
    print(f, o.read().decode())
c.close()
