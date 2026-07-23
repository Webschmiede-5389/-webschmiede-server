"""Ensure agency nginx serves root images before SPA fallback."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import paramiko
from agency_config import ssh_connect

SITE = "/etc/nginx/sites-available/digitalehandwerkskunst.de"
BLOCK = """
    location ~* ^/(webschmiede-icon|craftsman|vorher-screenshot|nachher-screenshot|christian-kummetat|site-overrides)\\.(png|jpg|jpeg|css|ico)$ {
        try_files $uri =404;
        expires 7d;
        add_header Cache-Control "public";
    }
"""

client = paramiko.SSHClient()
ssh_connect(client)
sftp = client.open_sftp()
with sftp.open(SITE, "r") as f:
    cfg = f.read().decode("utf-8")
if "webschmiede-icon" in cfg and "location ~*" in cfg:
    print("OK nginx already patched")
else:
    needle = "    location /assets/ {"
    if needle not in cfg:
        needle = "    # React/Vite SPA"
    cfg = cfg.replace(
        needle,
        BLOCK + "\n" + needle,
        1,
    )
    with sftp.open(SITE, "w") as f:
        f.write(cfg)
    print("PATCHED nginx")
sftp.close()
_, o, e = client.exec_command("nginx -t && systemctl reload nginx")
print(o.read().decode())
print(e.read().decode())
client.close()
