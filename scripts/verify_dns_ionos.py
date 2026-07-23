"""Verify DNS + nginx from server."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import paramiko
from agency_config import ssh_connect

client = paramiko.SSHClient()
ssh_connect(client)

def run(cmd):
    _, out, _ = client.exec_command(cmd, timeout=25)
    o = out.read().decode("utf-8", errors="replace").strip()
    print(f"$ {cmd}\n{o}\n")

run("dig +short digitalehandwerkskunst.de A @8.8.8.8")
run("dig +short www.digitalehandwerkskunst.de A @8.8.8.8")
run('curl -s -o /dev/null -w "agency-keys: %{http_code}" -H "Host: digitalehandwerkskunst.de" http://127.0.0.1/agency-keys')
run('curl -s -H "Host: digitalehandwerkskunst.de" http://127.0.0.1/agency-keys | grep -i title')
run('curl -s -o /dev/null -w "homepage: %{http_code}" -H "Host: digitalehandwerkskunst.de" http://127.0.0.1/')
run("nginx -T 2>/dev/null | grep -E 'listen 443|ssl_certificate' || echo 'NO SSL YET'")

client.close()
