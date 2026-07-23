#!/usr/bin/env python3
import sys, os
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agency_config import ssh_connect
import paramiko

c = paramiko.SSHClient()
ssh_connect(c, role="web")
_, o, _ = c.exec_command("sed -n '1,90p' /etc/nginx/sites-available/digitalehandwerkskunst.de")
text = o.read().decode("utf-8", errors="replace")
out = os.path.join(os.path.dirname(__file__), "..", "tmp_nginx_dhk.txt")
Path(out).write_text(text, encoding="utf-8")
print("written", out)
c.close()
