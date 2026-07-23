#!/usr/bin/env python3
"""
Agency-Domain: Cloudflare DNS prüfen + WAF/Bot-Schutz aktivieren.
Nameserver bei IONOS umstellen (Anleitung / falls API).

  python scripts/activate_agency_cloudflare_waf.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app" / "backend"))
from agency_config import _read_file_secrets

DOMAIN = "digitalehandwerkskunst.de"
ORIGIN = "167.233.150.230"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    from integrations.cloudflare_protect import (
        apply_protection_profile,
        ensure_a_record,
        ensure_zone,
        find_zone,
        token,
    )

    sec = _read_file_secrets()
    if not token(sec):
        print("CLOUDFLARE_API_TOKEN fehlt")
        return 1

    # DNS-Records aktualisieren (Origin = neuer Web)
    print("=== Zone ===")
    # reuse setup script logic via module
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "setup_cf", ROOT / "scripts" / "setup_agency_cloudflare_dns.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    # run record ensure by calling main pieces
    z = ensure_zone(DOMAIN, secrets=sec)
    if not z.get("ok"):
        print(z)
        return 1
    zone_id = z["zone_id"]
    print(f"zone_id={zone_id} status={z.get('status')}")
    ns = z.get("name_servers") or []
    print("Nameserver:")
    for n in ns:
        print(f"  {n}")

    tok = token(sec)
    for name, proxied in (
        (DOMAIN, True),
        (f"www.{DOMAIN}", True),
        (f"cal.{DOMAIN}", True),
        (f"yassine.{DOMAIN}", True),
        (f"muster.{DOMAIN}", True),
        (f"voice.{DOMAIN}", True),
        (f"*.{DOMAIN}", False),
    ):
        ensure_a_record(zone_id, name, ORIGIN, proxied=proxied, tok=tok)
        print(f"  A {name} -> {ORIGIN} proxied={proxied}")

    print("\n=== Schutzprofil ===")
    prot = apply_protection_profile(zone_id, tok=tok)
    print(json.dumps(prot.get("settings"), indent=2, ensure_ascii=False)[:1200])

    zone = find_zone(DOMAIN, tok) or {}
    status = zone.get("status")
    print(f"\nZone-Status: {status}")

    if status != "active":
        print("\n=== PFLICHT: Nameserver bei IONOS ===")
        print("Ohne NS-Umstellung greift Cloudflare (WAF) nicht.")
        print("IONOS → Domains → digitalehandwerkskunst.de → Nameserver:")
        for n in ns or zone.get("name_servers") or []:
            print(f"  {n}")
        print("Danach oft 1–24 Std bis Status Active.")
        print("A-Records bei IONOS werden dann egal – DNS liegt bei Cloudflare.")
    else:
        print("Zone Active – Traffic läuft bereits über Cloudflare.")

    # Real-IP Snippet für Nginx vorbereiten (lokal + Hinweis Deploy)
    cf_ips = """# Cloudflare Real-IP (damit Rate-Limits echte Client-IPs sehen)
# Quelle: https://www.cloudflare.com/ips/
set_real_ip_from 173.245.48.0/20;
set_real_ip_from 103.21.244.0/22;
set_real_ip_from 103.22.200.0/22;
set_real_ip_from 103.31.4.0/22;
set_real_ip_from 141.101.64.0/18;
set_real_ip_from 108.162.192.0/18;
set_real_ip_from 190.93.240.0/20;
set_real_ip_from 188.114.96.0/20;
set_real_ip_from 197.234.240.0/22;
set_real_ip_from 198.41.128.0/17;
set_real_ip_from 162.158.0.0/15;
set_real_ip_from 104.16.0.0/13;
set_real_ip_from 104.24.0.0/14;
set_real_ip_from 172.64.0.0/13;
set_real_ip_from 131.0.72.0/22;
set_real_ip_from 2400:cb00::/32;
set_real_ip_from 2606:4700::/32;
set_real_ip_from 2803:f800::/32;
set_real_ip_from 2405:b500::/32;
set_real_ip_from 2405:8100::/32;
set_real_ip_from 2a06:98c0::/29;
set_real_ip_from 2c0f:f248::/32;
real_ip_header CF-Connecting-IP;
"""
    snippet = ROOT / "infra" / "nginx" / "cloudflare-realip.conf"
    snippet.parent.mkdir(parents=True, exist_ok=True)
    snippet.write_text(cf_ips, encoding="utf-8")
    print(f"\nNginx Real-IP Snippet: {snippet}")

    # Upload + include on web
    try:
        import paramiko
        from agency_config import ssh_connect

        c = paramiko.SSHClient()
        ssh_connect(c, role="web")
        sftp = c.open_sftp()
        remote = "/etc/nginx/conf.d/cloudflare-realip.conf"
        with sftp.file(remote, "w") as f:
            f.write(cf_ips)
        sftp.close()
        _, o, e = c.exec_command("nginx -t && systemctl reload nginx", timeout=30)
        print((o.read() + e.read()).decode("utf-8", "replace")[-500:])
        c.close()
        print("Nginx Real-IP live auf web")
    except Exception as ex:
        print(f"Nginx Real-IP Upload spaeter: {ex}")

    print("\nFERTIG Agency Cloudflare-Schutz (Profil gesetzt).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
