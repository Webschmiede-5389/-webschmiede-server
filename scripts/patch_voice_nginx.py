#!/usr/bin/env python3
"""Patch web-01 nginx: voice-demo proxy -> new VOICE_HOST."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import paramiko
from agency_config import ssh_connect, target_secrets, _read_file_secrets

OLD_IP = "62.238.43.128"
SITE_PATHS = (
    "/etc/nginx/sites-available/digitalehandwerkskunst.de",
    "/etc/nginx/sites-enabled/digitalehandwerkskunst.de",
)


def main() -> int:
    new_ip = os.environ.get("VOICE_HOST") or _read_file_secrets().get("VOICE_HOST", "")
    if not new_ip:
        print("VOICE_HOST fehlt")
        return 1

    web = paramiko.SSHClient()
    ssh_connect(web, role="web")
    sftp = web.open_sftp()
    changed = False
    for site in SITE_PATHS:
        try:
            with sftp.open(site, "r") as f:
                cfg = f.read().decode("utf-8")
        except OSError:
            continue
        if f"http://{new_ip}:8090" in cfg and OLD_IP not in cfg:
            print(f"OK {site}")
            continue
        new_cfg = cfg.replace(f"http://{OLD_IP}:8090", f"http://{new_ip}:8090")
        if new_cfg == cfg:
            print(f"SKIP {site} (kein voice-demo block)")
            continue
        with sftp.open(site, "w") as f:
            f.write(new_cfg)
        print(f"PATCHED {site}")
        changed = True
    sftp.close()

    if changed:
        _, o, e = web.exec_command("nginx -t && systemctl reload nginx", timeout=20)
        print((o.read() or e.read()).decode())

    _, o, _ = web.exec_command(
        f'curl -sk -o /dev/null -w "%{{http_code}}" -H "Host: digitalehandwerkskunst.de" '
        f"https://127.0.0.1/voice-demo/api/health"
    )
    print(f"voice-demo proxy: HTTP {o.read().decode().strip()}")
    web.close()

    # UFW on voice: allow 8090 from web-01
    voice = paramiko.SSHClient()
    ssh_connect(voice, role="voice")
    web_ip = target_secrets("web")["SERVER_HOST"]
    voice.exec_command(
        f"ufw allow from {web_ip} to any port 8090 proto tcp 2>/dev/null; ufw allow 8090/tcp 2>/dev/null; true"
    )
    voice.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
