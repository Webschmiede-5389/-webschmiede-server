#!/usr/bin/env python3
"""Install Cal.com (Docker) + nginx /cal/ proxy on Webschmiede server."""
import os
import secrets
import sys
import time

import paramiko
from agency_config import ssh_connect, target_secrets

HOST = target_secrets("web")["SERVER_HOST"]
CAL_DIR = "/opt/calcom"
NGINX_SITE = "/etc/nginx/sites-available/snack-house"

NGINX_CAL = r"""
    # Cal.com 1:1 booking
    location /cal/ {
        proxy_pass         http://127.0.0.1:3000/;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_set_header   X-Forwarded-Host $host;
        proxy_read_timeout 300;
        proxy_redirect     / /cal/;
        proxy_redirect     http://$host/ /cal/;
        proxy_redirect     http://127.0.0.1:3000/ /cal/;
    }

    location = /cal {
        return 301 /cal/;
    }
"""


def connect():
    c = paramiko.SSHClient()
    ssh_connect(c, timeout=20, banner_timeout=20, role="web")
    return c


def run(client, cmd, timeout=180):
    _, out, err = client.exec_command(cmd, timeout=timeout)
    o = out.read().decode("utf-8", errors="replace").strip()
    e = err.read().decode("utf-8", errors="replace").strip()
    if o:
        sys.stdout.buffer.write(o.encode("utf-8", errors="replace"))
        sys.stdout.buffer.write(b"\n")
    if e and "WARNING" not in e.upper():
        print("ERR:", e[:500])
    return o


def main():
    pg_pass = secrets.token_urlsafe(18)
    next_secret = secrets.token_urlsafe(32)
    enc_key = secrets.token_hex(16)
    public_url = "https://cal.digitalehandwerkskunst.de"

    client = connect()

    print("=== Docker pruefen ===")
    docker_v = run(client, "docker -v 2>/dev/null || echo MISSING")
    if "MISSING" in docker_v:
        run(client, "apt-get update -qq && apt-get install -y -qq docker.io docker-compose-v2", timeout=300)
    run(client, "docker -v && docker compose version")

    print("\n=== Cal.com Verzeichnis ===")
    run(client, f"mkdir -p {CAL_DIR}")

    compose = f"""services:
  database:
    image: postgres:15-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: cal
      POSTGRES_PASSWORD: {pg_pass}
      POSTGRES_DB: calendso
    volumes:
      - cal_pg:/var/lib/postgresql/data

  calcom:
    image: calcom/cal.com:v6.2.0
    restart: unless-stopped
    depends_on:
      - database
    ports:
      - "127.0.0.1:3000:3000"
    environment:
      DATABASE_URL: postgresql://cal:{pg_pass}@database:5432/calendso
      DATABASE_DIRECT_URL: postgresql://cal:{pg_pass}@database:5432/calendso
      NEXTAUTH_SECRET: {next_secret}
      CALENDSO_ENCRYPTION_KEY: {enc_key}
      NEXT_PUBLIC_WEBAPP_URL: {public_url}
      NEXTAUTH_URL: {public_url}
      WEBAPP_URL: {public_url}
      TZ: Europe/Berlin

volumes:
  cal_pg:
"""
    sftp = client.open_sftp()
    with sftp.open(f"{CAL_DIR}/docker-compose.yml", "w") as f:
        f.write(compose)
    sftp.close()

    print("\n=== Cal.com starten (kann einige Minuten dauern) ===")
    run(client, f"cd {CAL_DIR} && docker compose pull", timeout=600)
    run(client, f"cd {CAL_DIR} && docker compose up -d", timeout=300)
    time.sleep(15)
    run(client, "docker compose -f /opt/calcom/docker-compose.yml ps")

    print("\n=== nginx: /cal/ ===")
    nginx = run(client, f"cat {NGINX_SITE}")
    if "location /cal/" not in nginx:
        marker = "    # Backend API Proxy"
        if marker in nginx:
            nginx = nginx.replace(marker, NGINX_CAL + "\n" + marker)
        else:
            nginx = nginx.replace("    location /api/ {", NGINX_CAL + "\n    location /api/ {")
        sftp = client.open_sftp()
        with sftp.open(NGINX_SITE, "w") as f:
            f.write(nginx)
        sftp.close()
        run(client, "nginx -t && systemctl reload nginx")

    print("\n=== Flask .env CALCOM_URL ===")
    run(
        client,
        f"grep -q '^CALCOM_URL=' /root/app/backend/.env 2>/dev/null && "
        f"sed -i 's|^CALCOM_URL=.*|CALCOM_URL={public_url}|' /root/app/backend/.env || "
        f"echo 'CALCOM_URL={public_url}' >> /root/app/backend/.env",
    )
    run(client, "systemctl restart snack-api")
    time.sleep(3)
    run(client, "systemctl is-active snack-api")

    cred_path = os.path.join(os.path.dirname(__file__), "calcom-credentials.local.txt")
    with open(cred_path, "w", encoding="utf-8") as f:
        f.write(f"Cal.com URL:     {public_url}\n")
        f.write(f"Postgres pass:   {pg_pass}\n")
        f.write(f"NEXTAUTH_SECRET: {next_secret}\n")
        f.write(f"Encryption key:  {enc_key}\n")
        f.write("\nErster Start: /cal/ im Browser oeffnen und Admin-Account anlegen.\n")
        f.write("Google Calendar: in Cal.com unter Settings > Calendars verbinden.\n")

    client.close()
    print("\n=== FERTIG ===")
    print(f"URL: {public_url}")
    print(f"Credentials: {cred_path}")
    print("Hinweis: Cal.com braucht beim ersten Start 1-3 Min. bis die UI antwortet.")


if __name__ == "__main__":
    main()
