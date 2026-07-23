#!/usr/bin/env python3
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agency_config import ssh_connect
import paramiko

c = paramiko.SSHClient()
ssh_connect(c, role="web")
_, o, _ = c.exec_command("grep -A8 'location /n8n' /etc/nginx/sites-enabled/digitalehandwerkskunst.de 2>/dev/null | head -12")
print(o.read().decode())
c.close()
