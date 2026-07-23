"""Cal.com unter https://cal.digitalehandwerkskunst.de (Google OAuth braucht TLD)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agency_config import ssh_connect
import paramiko

HOST = "cal.digitalehandwerkskunst.de"
PUBLIC = f"https://{HOST}"
SITE = f"/etc/nginx/sites-available/{HOST}"
ENABLED = f"/etc/nginx/sites-enabled/{HOST}"
EMAIL = "info@digitalehandwerkskunst.de"

NGINX = f"""
server {{
    listen 80;
    listen [::]:80;
    server_name {HOST};

    location / {{
        proxy_pass         http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_set_header   X-Forwarded-Host $host;
        proxy_read_timeout 300;
    }}
}}
"""


def run(c, cmd, timeout=180):
    print(">>>", cmd[:110])
    _, o, e = c.exec_command(cmd, timeout=timeout)
    out = (o.read() + e.read()).decode("utf-8", "replace")
    print(out[-2000:].encode("ascii", "replace").decode())
    return out


def main():
    c = paramiko.SSHClient()
    ssh_connect(c, timeout=30, banner_timeout=30)

    # Bind Cal.com only to localhost again (HTTPS via nginx)
    sftp = c.open_sftp()
    with sftp.open("/opt/calcom/docker-compose.yml") as f:
        compose = f.read().decode()
    compose = compose.replace('"3000:3000"', '"127.0.0.1:3000:3000"')
    compose = compose.replace("- 3000:3000", "- 127.0.0.1:3000:3000")
    lines = []
    for line in compose.splitlines():
        if any(
            line.strip().startswith(k + ":")
            for k in ("NEXT_PUBLIC_WEBAPP_URL", "NEXTAUTH_URL", "WEBAPP_URL")
        ):
            indent = line[: len(line) - len(line.lstrip())]
            key = line.strip().split(":", 1)[0]
            lines.append(f"{indent}{key}: {PUBLIC}")
        else:
            lines.append(line)
    compose = "\n".join(lines) + "\n"
    with sftp.open("/opt/calcom/docker-compose.yml", "w") as f:
        f.write(compose)

    with sftp.open(SITE, "w") as f:
        f.write(NGINX)
    sftp.close()

    run(c, f"ln -sf {SITE} {ENABLED}")
    run(c, "nginx -t && systemctl reload nginx")
    run(c, f"cd /opt/calcom && docker compose up -d --force-recreate calcom", timeout=180)
    time.sleep(20)

    # SSL
    run(
        c,
        f"certbot --nginx -d {HOST} --non-interactive --agree-tos -m {EMAIL} --redirect",
        timeout=180,
    )
    run(c, "nginx -t && systemctl reload nginx")

    run(
        c,
        f"grep -q '^CALCOM_URL=' /root/app/backend/.env && "
        f"sed -i 's|^CALCOM_URL=.*|CALCOM_URL={PUBLIC}|' /root/app/backend/.env || "
        f"echo 'CALCOM_URL={PUBLIC}' >> /root/app/backend/.env; "
        "systemctl restart snack-api; sleep 2; systemctl is-active snack-api",
    )

    run(c, f"curl -sI -m 15 {PUBLIC}/auth/setup | head -15")
    c.close()

    cred = Path(__file__).resolve().parents[1] / "calcom-credentials.local.txt"
    redirect1 = f"{PUBLIC}/api/integrations/googlecalendar/callback"
    redirect2 = f"{PUBLIC}/api/auth/callback/google"
    cred.write_text(
        f"Cal.com URL:     {PUBLIC}\n"
        f"Setup/Login:     {PUBLIC}/auth/setup\n"
        f"\nGoogle OAuth Redirect URIs:\n"
        f"  {redirect1}\n"
        f"  {redirect2}\n",
        encoding="utf-8",
    )
    print("OK", PUBLIC)
    print("REDIRECTS:")
    print(redirect1)
    print(redirect2)


if __name__ == "__main__":
    main()
