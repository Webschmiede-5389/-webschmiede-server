#!/usr/bin/env python3
"""Add /akquise route to all nginx vhosts on server."""
import os
import sys

import paramiko

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agency_config import ssh_connect

AKQUISE = """
    location = /akquise {
        root /var/www/snackhouse-mechernich;
        try_files /akquise-report.html =404;
    }
"""

SITES = [
    "/etc/nginx/sites-available/snack-house",
    "/etc/nginx/sites-available/digitalehandwerkskunst.de",
]


def main():
    c = paramiko.SSHClient()
    ssh_connect(c)
    sftp = c.open_sftp()

    for site in SITES:
        try:
            with sftp.open(site, "r") as f:
                cfg = f.read().decode("utf-8")
        except FileNotFoundError:
            print(f"SKIP {site}")
            continue
        if "location = /akquise" in cfg:
            print(f"OK {site}")
            continue
        if "location / {" in cfg:
            cfg = cfg.replace("    location / {", AKQUISE + "\n    location / {", 1)
        else:
            cfg = AKQUISE + cfg
        with sftp.open(site, "w") as f:
            f.write(cfg)
        print(f"PATCH {site}")

    sftp.close()
    _, o, e = c.exec_command("nginx -t && systemctl reload nginx")
    print(o.read().decode())
    err = e.read().decode()
    if err:
        print(err)
    _, o, _ = c.exec_command('curl -s -o /dev/null -w "%{http_code} %{size_download}" http://127.0.0.1/akquise')
    print("Test:", o.read().decode())
    c.close()


if __name__ == "__main__":
    main()
