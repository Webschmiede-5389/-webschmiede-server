"""Dump digitalehandwerkskunst nginx + test image URLs."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import paramiko
from agency_config import ssh_connect

client = paramiko.SSHClient()
ssh_connect(client)
for cmd in (
    "grep -n 'server_name\\|root\\|listen\\|webschmiede\\|try_files' /etc/nginx/sites-enabled/digitalehandwerkskunst.de | head -40",
    'curl -sk -o /dev/null -w "https icon: %{http_code} ct:%{content_type}\\n" https://digitalehandwerkskunst.de/webschmiede-icon.png',
    'curl -s -o /dev/null -w "http icon: %{http_code} ct:%{content_type}\\n" -H "Host: digitalehandwerkskunst.de" http://127.0.0.1/webschmiede-icon.png',
    "ls -la /var/www/digitalehandwerkskunst/webschmiede-icon.png",
):
    _, o, e = client.exec_command(cmd)
    print(o.read().decode())
    er = e.read().decode()
    if er:
        print("ERR:", er[:200])
client.close()
