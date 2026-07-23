"""Find which nginx config serves /agency-keys."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import paramiko
from agency_config import ssh_connect

client = paramiko.SSHClient()
ssh_connect(client)

def run(cmd):
    _, out, err = client.exec_command(cmd, timeout=30)
    o = out.read().decode("utf-8", errors="replace").strip()
    print(f"$ {cmd}\n{o}\n")
    return o

run("ls -la /etc/nginx/sites-enabled/")
run("nginx -T 2>/dev/null | grep -A2 'location = /agency-keys' || echo 'not in active config'")
run("nginx -T 2>/dev/null | grep -E 'server_name|root ' | head -40")
run("curl -sI http://127.0.0.1/agency-keys | head -15")
run("curl -s http://167.233.211.170/agency-keys 2>/dev/null | head -3 || curl -s --resolve 167.233.211.170:80:127.0.0.1 http://167.233.211.170/agency-keys | head -3")

client.close()
