"""Diagnose /agency-keys on server."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import paramiko
from agency_config import ssh_connect

client = paramiko.SSHClient()
ssh_connect(client)

def run(cmd):
    _, out, err = client.exec_command(cmd, timeout=20)
    o = out.read().decode("utf-8", errors="replace").strip()
    e = err.read().decode("utf-8", errors="replace").strip()
    print(f"$ {cmd}")
    if o:
        print(o)
    if e:
        print("ERR:", e[:500])
    print()
    return o

run("grep -n agency-keys /etc/nginx/sites-available/snack-house || echo 'NO ROUTE'")
run("test -f /var/www/snackhouse-mechernich/agency-keys.html && echo EXISTS || echo MISSING")
run("head -8 /var/www/snackhouse-mechernich/agency-keys.html 2>/dev/null || true")
run('curl -s http://127.0.0.1/agency-keys | head -5')
run('curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1/agency-keys')
run("systemctl is-active snack-api")
run("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/api/agency/secrets -H 'X-Agency-Password: x'")

client.close()
