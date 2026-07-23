"""Check all agency-keys URLs."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import paramiko
from agency_config import ssh_connect

client = paramiko.SSHClient()
ssh_connect(client)

def run(cmd):
    _, out, _ = client.exec_command(cmd, timeout=20)
    o = out.read().decode("utf-8", errors="replace").strip()
    print(f"$ {cmd}\n{o}\n")

run('curl -s -o /dev/null -w "localhost agency-keys: %{http_code}" http://127.0.0.1/agency-keys')
run('curl -s -o /dev/null -w "host snack agency-keys: %{http_code}" -H "Host: snack-house" http://127.0.0.1/agency-keys')
run('curl -s -o /dev/null -w "host dhk agency-keys: %{http_code}" -H "Host: digitalehandwerkskunst.de" http://127.0.0.1/agency-keys')
run('curl -s -o /dev/null -w "host dhk agency: %{http_code}" -H "Host: digitalehandwerkskunst.de" http://127.0.0.1/agency')
run('curl -sI -H "Host: digitalehandwerkskunst.de" http://127.0.0.1/agency-keys | head -5')
run('curl -s -H "Host: digitalehandwerkskunst.de" http://127.0.0.1/agency-keys | head -3')
run("nginx -T 2>/dev/null | grep -E 'listen 80|default_server|server_name' | head -20")
run("ls /etc/nginx/sites-enabled/")

client.close()
