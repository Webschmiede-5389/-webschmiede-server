#!/usr/bin/env python3
"""Add /agency-hub and /ci/ to digitalehandwerkskunst nginx if missing."""
import sys
import os
import paramiko

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agency_config import ssh_connect

SNACK = "/var/www/snackhouse-mechernich"
SITE = "/etc/nginx/sites-available/digitalehandwerkskunst.de"

HUB_BLOCK = f"""
    location = /agency-hub {{
        root {SNACK};
        try_files /agency-hub.html =404;
    }}
    location /ci/ {{
        root {SNACK};
        try_files $uri =404;
    }}
"""


def main():
    client = paramiko.SSHClient()
    ssh_connect(client)
    sftp = client.open_sftp()
    with sftp.open(SITE, "r") as f:
        cfg = f.read().decode("utf-8")

    if "location = /agency-hub" in cfg:
        print("OK agency-hub route exists")
    else:
        needle = "    location = /agency-setup {"
        if needle not in cfg:
            raise SystemExit("agency-setup block not found")
        cfg = cfg.replace(needle, HUB_BLOCK + needle, 1)
        with sftp.open(SITE, "w") as f:
            f.write(cfg)
        print("PATCHED agency-hub + /ci/")

    sftp.close()
    _, out, err = client.exec_command("nginx -t && systemctl reload nginx", timeout=20)
    print(out.read().decode() or err.read().decode())

    for path in ("/agency-hub", "/ci/rechnung-vorlage.html", "/ci/webschmiede-icon.png"):
        _, o, _ = client.exec_command(
            f'curl -sk -o /dev/null -w "{path}: %{{http_code}}\\n" '
            f'-H "Host: digitalehandwerkskunst.de" https://127.0.0.1{path}'
        )
        print(o.read().decode().strip())

    client.close()


if __name__ == "__main__":
    main()
