#!/usr/bin/env python3
import os
import sys

import paramiko

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency_config import ssh_connect

c = paramiko.SSHClient()
ssh_connect(c, timeout=45, banner_timeout=45, role="web")
_, o, _ = c.exec_command("cat /etc/nginx/sites-enabled/digitalehandwerkskunst.de")
data = o.read()
out = os.path.join(ROOT, "scripts", "_nginx_dhk.conf")
with open(out, "wb") as f:
    f.write(data)
print("wrote", out, "bytes", len(data))
c.close()
