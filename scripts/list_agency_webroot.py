"""List agency webroot files on server."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import paramiko
from agency_config import ssh_connect

WEBROOT = "/var/www/digitalehandwerkskunst"
client = paramiko.SSHClient()
ssh_connect(client)
for cmd in (
    f"ls -la {WEBROOT} 2>/dev/null | head -30",
    f"ls -la {WEBROOT}/assets 2>/dev/null | head -10",
    f"find {WEBROOT} -maxdepth 1 -type f \\( -name '*.png' -o -name '*.jpg' \\) 2>/dev/null",
):
    _, o, _ = client.exec_command(cmd)
    print(o.read().decode())
client.close()
