"""Fix duplicate akquise in dhk nginx and reload."""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import paramiko
from agency_config import ssh_connect

SITE = "/etc/nginx/sites-available/digitalehandwerkskunst.de"

client = paramiko.SSHClient()
ssh_connect(client)
sftp = client.open_sftp()

with sftp.open(SITE, "r") as f:
    cfg = f.read().decode("utf-8")

# Remove standalone akquise block (keep the one inside SNACK routes block)
standalone = """
    location = /akquise {
        root /var/www/snackhouse-mechernich;
        try_files /akquise-report.html =404;
    }

"""
if cfg.count("location = /akquise") > 1:
    cfg = cfg.replace(standalone, "", 1)
    print("Removed duplicate /akquise block")

with sftp.open(SITE, "w") as f:
    f.write(cfg)
sftp.close()

_, out, err = client.exec_command("nginx -t && systemctl reload nginx", timeout=20)
print(out.read().decode())
print(err.read().decode())

_, o, _ = client.exec_command(
    'curl -s -H "Host: digitalehandwerkskunst.de" http://127.0.0.1/agency-keys | grep -i title'
)
print("Title:", o.read().decode().strip())

client.close()
