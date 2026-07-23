#!/usr/bin/env python3
import paramiko, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agency_config import ssh_connect

c = paramiko.SSHClient()
ssh_connect(c)

def run(cmd):
    _, o, e = c.exec_command(cmd, timeout=30)
    print(o.read().decode(errors="replace"))
    err = e.read().decode(errors="replace")
    if err.strip():
        print("ERR:", err[:300])

run("ls -la /etc/nginx/sites-enabled/")
run("grep -rn akquise /etc/nginx/ 2>/dev/null | head -20")
run("ls -la /var/www/snackhouse-mechernich/akquise-report.html")
run('curl -s -o /dev/null -w "local akquise: %{http_code} size=%{size_download}\n" http://127.0.0.1/akquise')
c.close()
