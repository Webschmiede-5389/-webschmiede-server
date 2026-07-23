"""Add /onboarding to client subdomain nginx configs."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import paramiko
from agency_config import ssh_connect

BLOCK = """
    location = /onboarding {
        try_files /onboarding.html =404;
    }
"""

client = paramiko.SSHClient()
ssh_connect(client)
_, out, _ = client.exec_command("ls /etc/nginx/sites-available/kunde-*.digitalehandwerkskunst.de 2>/dev/null")
sites = [s.strip() for s in out.read().decode().splitlines() if s.strip()]
sftp = client.open_sftp()
for site in sites:
    with sftp.open(site, "r") as f:
        cfg = f.read().decode("utf-8")
    if "location = /onboarding" in cfg:
        print("OK", site)
        continue
    needle = "    location = /admin {\n        try_files /admin.html =404;\n    }"
    if needle in cfg and "location = /onboarding" not in cfg:
        cfg = cfg.replace(needle, needle + "\n" + BLOCK.strip(), 1)
        with sftp.open(site, "w") as f:
            f.write(cfg)
        print("PATCH", site)
sftp.close()
client.exec_command("nginx -t && systemctl reload nginx")
client.close()
print("Done")
