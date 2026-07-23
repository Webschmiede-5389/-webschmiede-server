"""Add /agency-setup to digitalehandwerkskunst nginx."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import paramiko
from agency_config import ssh_connect

ROUTE = """
    location = /agency-setup {
        root /var/www/snackhouse-mechernich;
        try_files /agency-setup.html =404;
    }
"""

SITE = "/etc/nginx/sites-available/digitalehandwerkskunst.de"
client = paramiko.SSHClient()
ssh_connect(client)
sftp = client.open_sftp()
with sftp.open(SITE, "r") as f:
    cfg = f.read().decode("utf-8")
if "location = /agency-setup" not in cfg:
    cfg = cfg.replace("    location = /agency-keys {", ROUTE + "\n    location = /agency-keys {", 1)
    with sftp.open(SITE, "w") as f:
        f.write(cfg)
    print("PATCH agency-setup on dhk")
else:
    print("OK")
sftp.close()
client.exec_command("nginx -t && systemctl reload nginx")
client.close()
