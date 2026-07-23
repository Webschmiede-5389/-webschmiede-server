#!/usr/bin/env python3
"""Add /nils to digitalehandwerkskunst nginx (SPA fängt sonst ab → Startseite)."""
import os
import sys

import paramiko

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agency_config import ssh_connect

SNACK = "/var/www/snackhouse-mechernich"
SITE_AVAILABLE = "/etc/nginx/sites-available/digitalehandwerkskunst.de"
SITE_ENABLED = "/etc/nginx/sites-enabled/digitalehandwerkskunst.de"
SITE_PATHS = (SITE_AVAILABLE, SITE_ENABLED)

NILS_BLOCK = f"""
    location = /nils {{
        root {SNACK};
        try_files /nils.html =404;
    }}
"""


def _patch_cfg(cfg: str) -> tuple[str, bool]:
    if "location = /nils" in cfg:
        return cfg, False
    needle = "    location = /agency-hub {"
    if needle not in cfg:
        needle = "    location = /agency-setup {"
    if needle not in cfg:
        raise RuntimeError("nginx anchor not found")
    return cfg.replace(needle, NILS_BLOCK + needle, 1), True


def main() -> int:
    client = paramiko.SSHClient()
    ssh_connect(client, role="web")
    sftp = client.open_sftp()
    changed = False
    for site in SITE_PATHS:
        try:
            with sftp.open(site, "r") as f:
                cfg = f.read().decode("utf-8")
        except OSError:
            print(f"SKIP {site} (nicht vorhanden)")
            continue
        cfg, did = _patch_cfg(cfg)
        if did:
            with sftp.open(site, "w") as f:
                f.write(cfg)
            print(f"PATCHED {site}")
            changed = True
        else:
            print(f"OK {site}")

    sftp.close()
    _, out, err = client.exec_command("nginx -t && systemctl reload nginx", timeout=20)
    print((out.read() or err.read()).decode())

    _, o, _ = client.exec_command(
        'curl -sk -H "Host: digitalehandwerkskunst.de" https://127.0.0.1/nils | grep -o "<title>[^<]*</title>" | head -1'
    )
    title = o.read().decode().strip()
    print(f"Test /nils: {title or 'NO TITLE'}")
    ok = "Nils" in title
    client.close()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
