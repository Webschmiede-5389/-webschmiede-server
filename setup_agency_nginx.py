#!/usr/bin/env python3
"""Nginx vhost + optional SSL for digitalehandwerkskunst.de on Hetzner."""
import os
import sys

import paramiko

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agency_config import load_secrets, ssh_connect

HOST = load_secrets()["SERVER_HOST"]
DOMAIN = "digitalehandwerkskunst.de"
WEBROOT = "/var/www/digitalehandwerkskunst"
NGINX_SITE = f"/etc/nginx/sites-available/{DOMAIN}"
NGINX_LINK = f"/etc/nginx/sites-enabled/{DOMAIN}"

NGINX_CONFIG = f"""server {{
    listen 80;
    listen [::]:80;
    server_name {DOMAIN} www.{DOMAIN};

    root {WEBROOT};
    index index.html;

    # Snack House / Agency (sonst fängt SPA ab → 404)
    location = /agency-keys {{
        root /var/www/snackhouse-mechernich;
        try_files /agency-keys.html =404;
    }}
    location = /agency {{
        root /var/www/snackhouse-mechernich;
        try_files /agency.html =404;
    }}
    location = /seminare {{
        root /var/www/snackhouse-mechernich;
        try_files /seminare.html =404;
    }}
    location = /akquise {{
        root /var/www/snackhouse-mechernich;
        try_files /akquise-report.html =404;
    }}
    location = /angebote {{
        try_files /angebote.html =404;
    }}
    location = /angebote.json {{
        try_files /angebote.json =404;
        add_header Cache-Control "public, max-age=300";
    }}
    location /ci/ {{
        try_files $uri =404;
        expires 7d;
    }}
    location /api/ {{
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 30;
    }}

    # React/Vite SPA
    location / {{
        try_files $uri $uri/ /index.html;
    }}

    location /assets/ {{
        expires 30d;
        add_header Cache-Control "public, immutable";
    }}

    location ~* ^/(webschmiede-icon|craftsman|vorher-screenshot|nachher-screenshot|christian-kummetat|favicon|site-overrides)\\.(png|jpg|jpeg|css|ico)$ {{
        try_files $uri =404;
        expires 7d;
        add_header Cache-Control "public";
    }}

    location = /favicon.ico {{ try_files $uri =404; }}
    location = /favicon.png {{ try_files $uri =404; }}

    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
}}
"""


def run(client, cmd, timeout=120):
    _, out, err = client.exec_command(cmd, timeout=timeout)
    o = out.read().decode("utf-8", errors="replace").strip()
    e = err.read().decode("utf-8", errors="replace").strip()
    if o:
        print(o)
    if e and "WARNING" not in e.upper() and "Saving debug log" not in e:
        print("ERR:", e[:500])
    return o


def main():
    ssl = "--ssl" in sys.argv

    client = paramiko.SSHClient()
    ssh_connect(client, timeout=20, banner_timeout=20)

    print("=== nginx vhost ===")
    sftp = client.open_sftp()
    with sftp.open(NGINX_SITE, "w") as f:
        f.write(NGINX_CONFIG)
    sftp.close()
    run(client, f"ln -sf {NGINX_SITE} {NGINX_LINK}")
    run(client, "nginx -t && systemctl reload nginx")

    run(client, f'test -f {WEBROOT}/index.html && echo "Webroot OK" || echo "FEHLER: Webroot leer — deploy_agency.py zuerst"')
    run(client, f'curl -s -o /dev/null -w "%{{http_code}}" -H "Host: {DOMAIN}" http://127.0.0.1/')

    if ssl:
        print("\n=== Let's Encrypt SSL ===")
        print("Hinweis: DNS muss bereits auf", HOST, "zeigen (A-Record).")
        email = os.environ.get("AGENCY_SSL_EMAIL", "info@digitalehandwerkskunst.de")
        run(
            client,
            f"certbot --nginx -d {DOMAIN} -d www.{DOMAIN} "
            f"--non-interactive --agree-tos -m {email} --redirect 2>&1 || "
            f"certbot certonly --nginx -d {DOMAIN} -d www.{DOMAIN} "
            f"--non-interactive --agree-tos -m {email} 2>&1",
            timeout=180,
        )
        run(client, "nginx -t && systemctl reload nginx")
    else:
        print("\nSSL: nach IONOS DNS-Umstellung:")
        print(f"  python setup_agency_nginx.py --ssl")

    client.close()
    print("\n=== IONOS DNS ===")
    print(f"  A  @   -> {HOST}")
    print(f"  A  www -> {HOST}")
    print("  Replit A-Record + replit-verify TXT entfernen")
    print(f"\nTest: http://{DOMAIN}/ (nach DNS-Propagation)")


if __name__ == "__main__":
    main()
