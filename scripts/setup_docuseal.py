#!/usr/bin/env python3
"""DocuSeal (e-sign) auf web-01: https://sign.digitalehandwerkskunst.de"""
from __future__ import annotations

import json
import secrets
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import paramiko
from agency_config import _read_file_secrets, ssh_connect, target_secrets

HOST = "sign.digitalehandwerkskunst.de"
PUBLIC = f"https://{HOST}"
DIR = "/opt/docuseal"
EMAIL = "info@digitalehandwerkskunst.de"
ORIGIN = target_secrets("web")["SERVER_HOST"]


def cf(method: str, path: str, token: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4{path}",
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def ensure_a(token: str, zone_id: str, name: str, ip: str) -> None:
    q = urllib.parse.quote(name)
    listed = cf("GET", f"/zones/{zone_id}/dns_records?type=A&name={q}", token)
    body = {"type": "A", "name": name, "content": ip, "ttl": 1, "proxied": True}
    for rec in listed.get("result") or []:
        if rec.get("name") == name:
            cf("PUT", f"/zones/{zone_id}/dns_records/{rec['id']}", token, body)
            print("CF updated", name)
            return
    cf("POST", f"/zones/{zone_id}/dns_records", token, body)
    print("CF created", name)


def run(c: paramiko.SSHClient, cmd: str, timeout: int = 300) -> str:
    print(">>>", cmd[:120])
    _, o, e = c.exec_command(cmd, timeout=timeout)
    out = (o.read() + e.read()).decode("utf-8", "replace")
    print(out[-1800:] if len(out) > 1800 else out)
    return out


def main() -> int:
    sec = _read_file_secrets()
    token = (sec.get("CLOUDFLARE_API_TOKEN") or "").strip()
    if not token:
        print("CLOUDFLARE_API_TOKEN fehlt")
        return 1
    zones = cf("GET", "/zones?name=digitalehandwerkskunst.de", token)
    zid = (zones.get("result") or [{}])[0].get("id")
    if not zid:
        print("Cloudflare Zone nicht gefunden")
        return 1
    ensure_a(token, zid, HOST, ORIGIN)

    secret = secrets.token_hex(64)
    compose = f"""services:
  docuseal:
    image: docuseal/docuseal:latest
    restart: unless-stopped
    ports:
      - "127.0.0.1:3002:3000"
    environment:
      SECRET_KEY_BASE: "{secret}"
      HOST: {HOST}
      FORCE_SSL: "true"
    volumes:
      - docuseal-data:/data
    mem_limit: 768m

volumes:
  docuseal-data:
"""
    nginx = f"""
server {{
    listen 80;
    listen [::]:80;
    server_name {HOST};

    client_max_body_size 50m;

    location / {{
        proxy_pass         http://127.0.0.1:3002;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 300;
    }}
}}
"""

    c = paramiko.SSHClient()
    ssh_connect(c, role="web")
    run(c, f"mkdir -p {DIR}")
    sftp = c.open_sftp()
    with sftp.file(f"{DIR}/docker-compose.yml", "w") as f:
        f.write(compose)
    with sftp.file(f"{DIR}/.credentials.local", "w") as f:
        f.write(f"URL={PUBLIC}\nSECRET_KEY_BASE={secret}\nSETUP=create admin on first visit\n")
    with sftp.file(f"/etc/nginx/sites-available/{HOST}", "w") as f:
        f.write(nginx)
    sftp.close()
    run(c, f"chmod 600 {DIR}/.credentials.local")
    run(c, f"ln -sf /etc/nginx/sites-available/{HOST} /etc/nginx/sites-enabled/{HOST}")
    run(c, f"cd {DIR} && docker compose pull", timeout=600)
    run(c, f"cd {DIR} && docker compose up -d", timeout=300)
    run(c, "nginx -t && systemctl reload nginx")
    time.sleep(8)
    run(
        c,
        f"certbot --nginx -d {HOST} --non-interactive --agree-tos -m {EMAIL} --redirect",
        timeout=180,
    )
    for _ in range(24):
        time.sleep(5)
        code = run(c, f"curl -s -o /dev/null -w '%{{http_code}}' http://127.0.0.1:3002/ || true")
        if any(x in code for x in ("200", "302", "301", "422")):
            break
    else:
        run(c, f"cd {DIR} && docker compose logs --tail 50")

    print("\nOK", PUBLIC)
    print("Beim ersten Öffnen Admin-Account anlegen.")
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
