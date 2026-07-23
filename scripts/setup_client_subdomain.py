#!/usr/bin/env python3
"""
Kunden-Subdomain unter digitalehandwerkskunst.de einrichten.

  python scripts/setup_client_subdomain.py SHY001 yassine --ssl   # Kunde
  python scripts/setup_client_subdomain.py --demo muster --ssl      # Demo (1× für alle)

IONOS DNS (vor --ssl):
  A  muster   →  167.233.150.230
  A  yassine  →  167.233.150.230
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import paramiko
from agency_config import load_secrets, ssh_connect

AGENCY_DOMAIN = "digitalehandwerkskunst.de"
DEMO_SUBDOMAIN = "muster"
DEMO_WEBROOT = "/var/www/snackhouse-mechernich"
KUNDEN_DIR = os.path.join(ROOT, "kunden")
SSL_EMAIL = "info@digitalehandwerkskunst.de"
ENV_PATH = "/root/app/backend/.env"
WEB_IP = "167.233.150.230"


def load_kunde(kid: str) -> tuple[dict, str]:
    kid = kid.upper()
    for fname in os.listdir(KUNDEN_DIR):
        if fname.endswith(".json") and fname.startswith(kid):
            path = os.path.join(KUNDEN_DIR, fname)
            with open(path, encoding="utf-8") as f:
                return json.load(f), path
    raise SystemExit(f"Kunde {kid} nicht in kunden/")


def nginx_config(host: str, webroot: str) -> str:
    return f"""server {{
    listen 80;
    listen [::]:80;
    server_name {host};

    root {webroot};
    index index.html;

    location = /bestellen {{
        try_files /order.html =404;
    }}
    location = /admin {{
        try_files /admin.html =404;
    }}
    location = /onboarding {{
        try_files /onboarding.html =404;
    }}
    location = /datenschutz {{
        try_files /datenschutz.html =404;
    }}
    location = /impressum {{
        try_files /impressum.html =404;
    }}

    location /api/ {{
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 30;
    }}

    location / {{
        try_files $uri $uri/ /index.html;
    }}

    location = /robots.txt {{
        add_header Content-Type text/plain;
        return 200 "User-agent: *\\nDisallow: /admin\\nDisallow: /api/\\n";
    }}

    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=(), interest-cohort=()" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com; style-src 'self' 'unsafe-inline' https://fonts.bunny.net https://cdnjs.cloudflare.com; font-src 'self' https://fonts.bunny.net https://cdnjs.cloudflare.com; img-src 'self' data: https://images.unsplash.com https://files.catbox.moe; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self';" always;
}}
"""


def ssh_run(client, cmd: str, timeout: int = 120) -> str:
    _, out, err = client.exec_command(cmd, timeout=timeout)
    o = out.read().decode("utf-8", errors="replace").strip()
    e = err.read().decode("utf-8", errors="replace").strip()
    safe = lambda s: s.encode("ascii", "replace").decode()
    if o:
        print(safe(o))
    if e and "Saving debug log" not in e:
        print("ERR:", safe(e[:600]))
    return o


def set_env_var(client, key: str, val: str):
    safe = str(val).replace("'", "'\"'\"'")
    ssh_run(
        client,
        f"grep -q '^{key}=' {ENV_PATH} 2>/dev/null && "
        f"sed -i 's|^{key}=.*|{key}={safe}|' {ENV_PATH} || "
        f"echo '{key}={safe}' >> {ENV_PATH}",
    )


def merge_cors(client, *hosts: str):
    """CORS um http(s)://host erweitern, PUBLIC_BASE_URL unverändert lassen."""
    bases = {
        "http://167.233.150.230",
        "https://167.233.150.230",
        "https://digitalehandwerkskunst.de",
        f"http://{DEMO_SUBDOMAIN}.{AGENCY_DOMAIN}",
        f"https://{DEMO_SUBDOMAIN}.{AGENCY_DOMAIN}",
    }
    for h in hosts:
        bases.add(f"http://{h}")
        bases.add(f"https://{h}")
    raw = ssh_run(client, f"grep '^CORS_ORIGINS=' {ENV_PATH} 2>/dev/null || true")
    if raw and "=" in raw:
        for part in raw.split("=", 1)[1].split(","):
            p = part.strip().rstrip("/")
            if p:
                bases.add(p)
    pub = ssh_run(client, f"grep '^PUBLIC_BASE_URL=' {ENV_PATH} 2>/dev/null || true")
    if pub and "=" in pub:
        p = pub.split("=", 1)[1].strip().rstrip("/")
        if p:
            bases.add(p)
    set_env_var(client, "CORS_ORIGINS", ",".join(sorted(bases)))


def deploy_nginx(client, sub: str, host: str, webroot: str, ssl: bool):
    site = f"/etc/nginx/sites-available/kunde-{sub}.{AGENCY_DOMAIN}"
    enabled = f"/etc/nginx/sites-enabled/kunde-{sub}.{AGENCY_DOMAIN}"
    sftp = client.open_sftp()
    with sftp.open(site, "w") as f:
        f.write(nginx_config(host, webroot))
    sftp.close()
    ssh_run(client, f"ln -sf {site} {enabled}")
    ssh_run(client, "nginx -t && systemctl reload nginx")
    if ssl:
        ssh_run(
            client,
            f"certbot --nginx -d {host} --non-interactive --agree-tos "
            f"-m {SSL_EMAIL} --redirect 2>&1 || true",
            timeout=180,
        )
        ssh_run(client, "nginx -t && systemctl reload nginx")
    code = ssh_run(
        client,
        f'curl -s -o /dev/null -w "%{{http_code}}" -H "Host: {host}" http://127.0.0.1/',
    )
    return code


def main():
    ap = argparse.ArgumentParser(description="Kunden-Subdomain einrichten")
    ap.add_argument("kunde_id", nargs="?", help="z.B. SHY001 (nicht nötig mit --demo)")
    ap.add_argument("subdomain", nargs="?", help="z.B. yassine")
    ap.add_argument("--demo", action="store_true", help="Nur Demo-Subdomain (kein Kunden-JSON / kein PUBLIC_BASE_URL)")
    ap.add_argument("--ssl", action="store_true", help="Let's Encrypt Zertifikat anfordern")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.demo:
        sub = (args.subdomain or DEMO_SUBDOMAIN).strip().lower()
        webroot = DEMO_WEBROOT
        label = f"Demo ({sub})"
        kunde, kpath = None, None
    else:
        if not args.kunde_id or not args.subdomain:
            raise SystemExit("Kunde: python scripts/setup_client_subdomain.py SHY001 yassine [--ssl]")
        kunde, kpath = load_kunde(args.kunde_id)
        sub = args.subdomain.strip().lower()
        webroot = kunde.get("server", {}).get("ordner", DEMO_WEBROOT)
        label = f"{kunde['name']} ({kunde['id']})"

    if not sub or "." in sub:
        raise SystemExit("Subdomain nur ein Label, z.B. yassine oder muster")

    host = f"{sub}.{AGENCY_DOMAIN}"
    base_https = f"https://{host}"

    print(f"=== {label} ===")
    print(f"Host:      {host}")
    print(f"Webroot:   {webroot}")
    print(f"Bestellen: {base_https}/bestellen")
    print()
    print("IONOS DNS:")
    print(f"  Typ A  | Hostname: {sub}  | Wert: {WEB_IP}")
    print(f"  (oder Wildcard * -> {WEB_IP} - dann kein IONOS-Schritt pro Kunde)")
    print()

    if args.dry_run:
        return

    client = paramiko.SSHClient()
    ssh_connect(client, role="web")

    deploy_nginx(client, sub, host, webroot, args.ssl)

    if args.demo:
        merge_cors(client, host)
        ssh_run(client, "systemctl restart snack-api")
    else:
        set_env_var(client, "PUBLIC_BASE_URL", base_https)
        set_env_var(client, "ORDER_PORTAL_URL", f"{base_https}/bestellen")
        merge_cors(client, host)
        ssh_run(client, "systemctl restart snack-api")
        ssh_run(client, "systemctl is-active snack-api")

        kunde.setdefault("urls", {})
        kunde["urls"]["subdomain"] = sub
        kunde["urls"]["demo_url"] = f"https://{DEMO_SUBDOMAIN}.{AGENCY_DOMAIN}/"
        kunde["urls"]["test_hauptseite"] = f"{base_https}/"
        kunde["urls"]["test_bestellen"] = f"{base_https}/bestellen"
        kunde["urls"]["test_admin"] = f"{base_https}/admin"
        with open(kpath, "w", encoding="utf-8") as f:
            json.dump(kunde, f, ensure_ascii=False, indent=2)
        print(f"\nGespeichert: {kpath}")

    client.close()
    print(f"\nTest (nach DNS): {base_https}/")
    if not args.ssl:
        flag = "--demo " if args.demo else f"{args.kunde_id} "
        print(f"Danach SSL: python scripts/setup_client_subdomain.py {flag}{sub} --ssl")


if __name__ == "__main__":
    main()
