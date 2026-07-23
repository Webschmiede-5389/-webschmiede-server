"""Dump full agency nginx config and debug image serving."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import paramiko
from agency_config import ssh_connect

client = paramiko.SSHClient()
ssh_connect(client)
cmds = [
    "wc -c /var/www/digitalehandwerkskunst/index.html /var/www/digitalehandwerkskunst/webschmiede-icon.png",
    "curl -sk -D - https://digitalehandwerkskunst.de/webschmiede-icon.png -o /tmp/icon.bin | head -15",
    "xxd /tmp/icon.bin | head -3",
    "nginx -T 2>/dev/null | sed -n '/server_name digitalehandwerkskunst/,/^}/p' | head -80",
]
for cmd in cmds:
    print("===", cmd[:70])
    _, o, e = client.exec_command(cmd)
    print(o.read().decode()[:2000])
    er = e.read().decode()
    if er:
        print("ERR", er[:200])
client.close()
