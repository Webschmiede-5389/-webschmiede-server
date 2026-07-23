#!/usr/bin/env python3
"""Agency-/API-Routen in digitalehandwerkskunst.de nginx (SPA fängt sonst ab → 404)."""
import os
import sys

import paramiko

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agency_config import ssh_connect

SNACK = "/var/www/snackhouse-mechernich"

ROUTES = f"""
    # Snack House / Agency (statisch aus {SNACK})
    location = /bestellen {{
        root {SNACK};
        try_files /order.html =404;
    }}
    location = /admin {{
        root {SNACK};
        try_files /admin.html =404;
    }}
    location = /seminare {{
        root {SNACK};
        try_files /seminare.html =404;
    }}
    location = /agency {{
        root {SNACK};
        try_files /agency.html =404;
    }}
    location = /agency-setup {{
        root {SNACK};
        try_files /agency-setup.html =404;
    }}
    location = /agency-hub {{
        root {SNACK};
        try_files /agency-hub.html =404;
    }}
    location = /nils {{
        root {SNACK};
        try_files /nils.html =404;
    }}
    location /ci/ {{
        root {SNACK};
        try_files $uri =404;
    }}

    location /api/ {{
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 30;
    }}
"""

AKQUISE = f"""
    location = /akquise {{
        root {SNACK};
        try_files /akquise-report.html =404;
    }}
"""

SITE = "/etc/nginx/sites-available/digitalehandwerkskunst.de"
MARKER = "location = /agency-keys"


def patch(cfg: str) -> str:
    if MARKER in cfg:
        return cfg
    needle = "    location / {"
    if needle not in cfg:
        raise RuntimeError("location / { nicht gefunden")
    block = ROUTES
    if "location = /akquise" not in cfg:
        block = AKQUISE + block
    return cfg.replace(needle, block + "\n" + needle, 1)


def main():
    client = paramiko.SSHClient()
    ssh_connect(client)
    sftp = client.open_sftp()

    with sftp.open(SITE, "r") as f:
        cfg = f.read().decode("utf-8")

    if MARKER in cfg:
        print(f"OK {SITE} (bereits gepatcht)")
    else:
        cfg = patch(cfg)
        with sftp.open(SITE, "w") as f:
            f.write(cfg)
        print(f"PATCH {SITE}")

    sftp.close()
    _, out, err = client.exec_command("nginx -t && systemctl reload nginx", timeout=20)
    print(out.read().decode())
    e = err.read().decode()
    if e:
        print(e)

    for path in ("/agency-keys", "/agency", "/api/seminars"):
        _, o, _ = client.exec_command(
            f'curl -s -o /dev/null -w "%{{http_code}}" -H "Host: digitalehandwerkskunst.de" '
            f"http://127.0.0.1{path}"
        )
        print(f"Test {path}: {o.read().decode().strip()}")

    _, o, _ = client.exec_command(
        f'curl -s -H "Host: digitalehandwerkskunst.de" http://127.0.0.1/agency-keys | head -8'
    )
    print(o.read().decode())

    client.close()
    print("Fertig.")


if __name__ == "__main__":
    main()
