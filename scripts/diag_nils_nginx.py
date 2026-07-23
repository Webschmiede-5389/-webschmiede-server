#!/usr/bin/env python3
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agency_config import ssh_connect
import paramiko

c = paramiko.SSHClient()
ssh_connect(c, role="web")
cmds = [
    "grep -n 'location.*nils\\|location / {\\|location = /agency' /etc/nginx/sites-available/digitalehandwerkskunst.de | head -40",
    "ls -la /var/www/snackhouse-mechernich/nils.html",
    'curl -sk -H "Host: digitalehandwerkskunst.de" https://127.0.0.1/nils | grep -o "<title>[^<]*</title>"',
    'curl -s -H "Host: digitalehandwerkskunst.de" http://127.0.0.1/nils | grep -o "<title>[^<]*</title>"',
    'curl -sk -H "Host: digitalehandwerkskunst.de" https://127.0.0.1/nils.html | grep -o "<title>[^<]*</title>"',
]
for cmd in cmds:
    print("---", cmd)
    _, o, e = c.exec_command(cmd)
    print(o.read().decode() or e.read().decode())
c.close()
