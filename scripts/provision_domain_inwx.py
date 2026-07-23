#!/usr/bin/env python3
"""
Domain bei INWX kaufen + A-Records auf web-01 setzen + optional Nginx/SSL.

Voraussetzung in deploy.secrets.local:
  INWX_USER, INWX_PASSWORD, INWX_CONTACT_ID, WEB_HOST

  python scripts/provision_domain_inwx.py snackhouse-yassine.de
  python scripts/provision_domain_inwx.py snackhouse-yassine.de --ssl
  python scripts/provision_domain_inwx.py snackhouse-yassine.de --dns-only
  python scripts/provision_domain_inwx.py snackhouse-yassine.de --no-cloudflare
  python scripts/provision_domain_inwx.py --test

Standard: Cloudflare Proxy/WAF. --no-cloudflare = nur INWX-DNS.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app" / "backend"))

from agency_config import _read_file_secrets, ssh_connect, target_secrets
import paramiko

from integrations.inwx import InwxClient, purchase_and_point, test_connection


def _stdout_safe() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def update_kunde(domain: str, purchase: dict, web_ip: str) -> None:
    path = ROOT / "kunden" / "SHY001_snackhouse.json"
    if not path.exists():
        return
    k = json.loads(path.read_text(encoding="utf-8"))
    k.setdefault("domain", {})
    k["domain"]["selected"] = domain
    k["domain"]["status"] = purchase.get("status") or "pending"
    k["domain"]["purchase"] = {
        "status": purchase.get("status"),
        "message": purchase.get("message"),
        "provider": "inwx",
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    cf = purchase.get("cloudflare") or {}
    ns = cf.get("name_servers") or ["ns.inwx.de", "ns2.inwx.de", "ns3.inwx.eu"]
    k["domain"]["inwx"] = {"origin": web_ip, "ns": ns}
    if cf.get("ok"):
        k["domain"]["cloudflare"] = {
            "zone_id": cf.get("zone_id"),
            "proxied": True,
            "name_servers": cf.get("name_servers") or [],
            "status": cf.get("status"),
        }
    k["urls"]["domain"] = domain
    k["urls"]["live_hauptseite"] = f"https://{domain}/"
    k["urls"]["live_bestellen"] = f"https://{domain}/bestellen"
    k["urls"]["live_admin"] = f"https://{domain}/admin"
    k["server"]["ip"] = web_ip
    pts = [p for p in (k.get("offene_punkte") or []) if "Domain" not in p]
    if purchase.get("status") not in ("purchased", "dns_updated"):
        pts.insert(0, f"Domain {domain}: {purchase.get('message')}")
    k["offene_punkte"] = pts
    path.write_text(json.dumps(k, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Updated {path.name}")


def ensure_nginx_ssl(domain: str, *, do_ssl: bool) -> None:
    cfg = f"""server {{
    listen 80;
    listen [::]:80;
    server_name {domain} www.{domain};
    root /var/www/snackhouse-mechernich;
    index index.html;
    location = /bestellen {{ try_files /order.html =404; }}
    location = /admin {{ try_files /admin.html =404; }}
    location = /onboarding {{ try_files /onboarding.html =404; }}
    location /api/ {{
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
    location / {{ try_files $uri $uri/ /index.html; }}
}}
"""
    c = paramiko.SSHClient()
    ssh_connect(c, role="web")
    site = f"/etc/nginx/sites-available/{domain}"
    sftp = c.open_sftp()
    with sftp.file(site, "w") as f:
        f.write(cfg)
    sftp.close()
    _, o, e = c.exec_command(
        f"ln -sfn {site} /etc/nginx/sites-enabled/{domain} && nginx -t && systemctl reload nginx",
        timeout=30,
    )
    print((o.read() + e.read()).decode("utf-8", "replace"))
    if do_ssl:
        _, o, e = c.exec_command(
            f"certbot --nginx -d {domain} -d www.{domain} "
            f"--non-interactive --agree-tos -m info@digitalehandwerkskunst.de --redirect",
            timeout=180,
        )
        print((o.read() + e.read()).decode("utf-8", "replace")[-1200:])
    c.close()


def main() -> int:
    _stdout_safe()
    args = sys.argv[1:]
    if "--test" in args or (args and args[0] == "test"):
        r = test_connection()
        print(json.dumps(r, indent=2, ensure_ascii=False))
        return 0 if r.get("ok") else 1

    domain = ""
    for a in args:
        if not a.startswith("-") and "." in a:
            domain = a.lower().strip()
            break
    if not domain:
        print(
            "Usage: python scripts/provision_domain_inwx.py snackhouse-yassine.de "
            "[--ssl] [--dns-only] [--no-cloudflare]"
        )
        print("       python scripts/provision_domain_inwx.py --test")
        return 1

    secrets = _read_file_secrets()
    web_ip = secrets.get("WEB_HOST") or target_secrets("web")["SERVER_HOST"]
    dns_only = "--dns-only" in args
    do_ssl = "--ssl" in args
    via_cf = "--no-cloudflare" not in args

    client = InwxClient(secrets=secrets)
    if not client.configured():
        print("INWX_USER / INWX_PASSWORD fehlen in deploy.secrets.local")
        print("Siehe docs/agency/inwx-domains.md")
        return 1
    if not client.contact_id and not dns_only:
        print("INWX_CONTACT_ID fehlt (Kontakt-Handle im INWX-Panel)")
        return 1

    if dns_only:
        print(f"DNS only: {domain} -> {web_ip} (cloudflare={via_cf})")
        if via_cf:
            from integrations.cloudflare_protect import provision_customer_domain

            cf = provision_customer_domain(domain, web_ip, secrets=secrets)
            r = {
                "status": "dns_updated",
                "message": "dns-only cloudflare",
                "cloudflare": cf,
            }
            if cf.get("ok") and cf.get("name_servers"):
                try:
                    client.set_nameservers(domain, cf["name_servers"])
                    r["message"] += "; NS gesetzt"
                except Exception as e:
                    r["message"] += f"; NS manuell: {cf['name_servers']} ({e})"
        else:
            r = {"status": "dns_updated", "message": "dns-only", **client.point_web_to_ip(domain, web_ip)}
    else:
        print(f"Kauf + DNS: {domain} -> {web_ip} (cloudflare={via_cf})")
        r = purchase_and_point(domain, web_ip, secrets=secrets, via_cloudflare=via_cf)

    print(json.dumps({k: v for k, v in r.items() if k != "raw"}, indent=2, ensure_ascii=False, default=str)[:2000])
    if r.get("status") in ("purchased", "dns_updated"):
        update_kunde(domain, r, web_ip)
        ensure_nginx_ssl(domain, do_ssl=do_ssl)
        if not do_ssl:
            print(f"\nSpaeter SSL: python scripts/provision_domain_inwx.py {domain} --ssl")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
