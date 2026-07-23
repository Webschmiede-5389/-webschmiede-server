"""Verify agency-setup portal on server."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import paramiko
from agency_config import ssh_connect

client = paramiko.SSHClient()
ssh_connect(client)

def run(cmd):
    _, o, _ = client.exec_command(cmd)
    print(o.read().decode().strip())

H = '--resolve digitalehandwerkskunst.de:443:127.0.0.1'
run(f'curl -sk -o /dev/null -w "https agency-setup: %{{http_code}}" {H} https://digitalehandwerkskunst.de/agency-setup')
print()
run(f'curl -sk {H} https://digitalehandwerkskunst.de/agency-setup | grep -i title')
run(f'curl -sk -o /dev/null -w "https agency-keys: %{{http_code}}" {H} https://digitalehandwerkskunst.de/agency-keys')
print()
run(f'curl -sk -o /dev/null -w "https api secrets: %{{http_code}}" {H} https://digitalehandwerkskunst.de/api/agency/secrets -H "X-Agency-Password: x"')
print()
run('test -f /var/www/snackhouse-mechernich/agency-setup.html && echo file:OK || echo file:MISSING')
client.close()
