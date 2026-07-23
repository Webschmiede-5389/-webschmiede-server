#!/usr/bin/env python3
"""
SHY001 Custom-Domain vorbereiten: Cloudflare-Zone + Nginx auf web-01.
Kauf .de: manuell bei IONOS (Cloudflare Registrar kann .de nicht).

  python scripts/setup_shy001_domain.py snackhouse-yacine.de
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agency_config import _read_file_secrets, ssh_connect, target_secrets

KUNDE_PATH = ROOT / "kunden" / "SHY001_snackhouse.json"
WEBROOT = "/var/www/snackhouse-mechernich"
SSL_EMAIL = "info@digitalehandwerkskunst.de"


def _stdout_safe() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def cf(method: str, path: str, token: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4{path}",
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"CF {method} {path}: {e.code} {e.read().decode()[:600]}") from e


def ensure_a(token: str, zone_id: str, name: str, ip: str, proxied: bool) -> None:
    q = urllib.parse.quote(name)
    listed = cf("GET", f"/zones/{zone_id}/dns_records?type=A&name={q}", token)
    for rec in listed.get("result") or []:
        cf(
            "PUT",
            f"/zones/{zone_id}/dns_records/{rec['id']}",
            token,
            {"type": "A", "name": name, "content": ip, "ttl": 1, "proxied": proxied},
        )
        print(f"  A {name} updated")
        return
    cf(
        "POST",
        f"/zones/{zone_id}/dns_records",
        token,
        {"type": "A", "name": name, "content": ip, "ttl": 1, "proxied": proxied},
    )
    print(f"  A {name} created")


def nginx_http(domain: str) -> str:
    return f"""server {{
    listen 80;
    listen [::]:80;
    server_name {domain} www.{domain};

    root {WEBROOT};
    index index.html;

    location = /bestellen {{ try_files /order.html =404; }}
    location = /admin {{ try_files /admin.html =404; }}
    location = /onboarding {{ try_files /onboarding.html =404; }}
    location = /datenschutz {{ try_files /datenschutz.html =404; }}
    location = /impressum {{ try_files /impressum.html =404; }}

    location /api/ {{
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 30;
    }}

    location / {{
        try_files $uri $uri/ /index.html;
    }}
}}
"""


def update_kunde(domain: str, web_ip: str, nameservers: list[str]) -> None:
    k = json.loads(KUNDE_PATH.read_text(encoding="utf-8"))
    k["domain"]["selected"] = domain
    k["domain"]["wish"] = domain
    k["domain"]["status"] = "pending_purchase"
    k["domain"]["selected_at"] = __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    k["domain"]["cloudflare"] = {
        "nameservers": nameservers,
        "origin": web_ip,
    }
    k["urls"]["domain"] = domain
    k["urls"]["live_hauptseite"] = f"https://{domain}/"
    k["urls"]["live_bestellen"] = f"https://{domain}/bestellen"
    k["urls"]["live_admin"] = f"https://{domain}/admin"
    k["server"]["ip"] = web_ip
    pts = k.get("offene_punkte") or []
    pts = [p for p in pts if "Domain" not in p]
    pts.insert(0, f"Domain {domain}: bei IONOS kaufen, Nameserver auf Cloudflare setzen")
    k["offene_punkte"] = pts
    KUNDE_PATH.write_text(json.dumps(k, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Updated {KUNDE_PATH.name}")


def main() -> int:
    _stdout_safe()
    domain = (sys.argv[1] if len(sys.argv) > 1 else "snackhouse-yacine.de").strip().lower()
    if not domain.endswith(".de"):
        print("Nur .de in diesem Skript (Kauf manuell)")
        return 1

    secrets = _read_file_secrets()
    token = secrets.get("CLOUDFLARE_API_TOKEN", "")
    account = secrets.get("CLOUDFLARE_ACCOUNT_ID", "")
    web = target_secrets("web")
    web_ip = web["SERVER_HOST"]
    if not token or not account:
        print("CLOUDFLARE_API_TOKEN / ACCOUNT_ID fehlt")
        return 1

    # Zone
    zones = cf("GET", f"/zones?name={domain}", token)
    results = zones.get("result") or []
    if results:
        zone = results[0]
        print(f"Zone existiert: {zone['id']} status={zone.get('status')}")
    else:
        created = cf(
            "POST",
            "/zones",
            token,
            {"name": domain, "account": {"id": account}, "jump_start": False, "type": "full"},
        )
        if not created.get("success"):
            print(created)
            return 1
        zone = created["result"]
        print(f"Zone angelegt: {zone['id']}")

    zone_id = zone["id"]
    ns = zone.get("name_servers") or []
    print("Nameserver:")
    for n in ns:
        print(f"  {n}")

    print(f"\nDNS -> {web_ip}")
    ensure_a(token, zone_id, domain, web_ip, True)
    ensure_a(token, zone_id, f"www.{domain}", web_ip, True)
    cf("PATCH", f"/zones/{zone_id}/settings/ssl", token, {"value": "full"})

    # Nginx
    site = f"/etc/nginx/sites-available/{domain}"
    enabled = f"/etc/nginx/sites-enabled/{domain}"
    cfg = nginx_http(domain)
    c = paramiko.SSHClient()
    ssh_connect(c, role="web")
    sftp = c.open_sftp()
    with sftp.file(site, "w") as f:
        f.write(cfg)
    sftp.close()
    _, o, e = c.exec_command(
        f"ln -sfn {site} {enabled} && nginx -t && systemctl reload nginx",
        timeout=30,
    )
    print((o.read() + e.read()).decode("utf-8", "replace"))

    # SSL erst wenn DNS auf Cloudflare zeigt (Domain gekauft + NS)
    do_ssl = "--ssl" in sys.argv
    if do_ssl:
        _, o, e = c.exec_command(
            f"certbot --nginx -d {domain} -d www.{domain} "
            f"--non-interactive --agree-tos -m {SSL_EMAIL} --redirect",
            timeout=180,
        )
        print((o.read() + e.read()).decode("utf-8", "replace")[-1500:])
    else:
        print("SSL noch nicht: erst Domain kaufen + NS umstellen, dann: "
              f"python scripts/setup_shy001_domain.py {domain} --ssl")

    c.close()
    update_kunde(domain, web_ip, ns)

    print("\n=== CHRISTIAN: Domain kaufen (IONOS) ===")
    print(f"1. Bei IONOS {domain} registrieren (~5-10 EUR/Jahr)")
    print("2. Nameserver setzen auf:")
    for n in ns:
        print(f"   {n}")
    print("3. Danach: python scripts/setup_shy001_domain.py " + domain + " --ssl")
    print("Subdomain yassine.digitalehandwerkskunst.de bleibt parallel erreichbar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
