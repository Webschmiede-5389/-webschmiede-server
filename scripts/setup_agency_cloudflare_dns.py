#!/usr/bin/env python3
"""Create Cloudflare zone for agency domain + A records. Prints nameservers for IONOS."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agency_config import _read_file_secrets

DOMAIN = "digitalehandwerkskunst.de"
ORIGIN = "167.233.150.230"  # web-01neu Nürnberg


def cf(method: str, path: str, token: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", "replace")
        raise SystemExit(f"Cloudflare {method} {path}: {e.code} {err[:800]}") from e


def ensure_record(token: str, zone_id: str, rtype: str, name: str, content: str, proxied: bool = True) -> None:
    # list existing
    q = urllib.parse.quote(name)
    listed = cf("GET", f"/zones/{zone_id}/dns_records?type={rtype}&name={q}", token)
    for rec in listed.get("result") or []:
        if rec.get("type") == rtype and rec.get("name") == name:
            rid = rec["id"]
            cf(
                "PUT",
                f"/zones/{zone_id}/dns_records/{rid}",
                token,
                {
                    "type": rtype,
                    "name": name,
                    "content": content,
                    "ttl": 1,
                    "proxied": proxied if rtype in ("A", "AAAA", "CNAME") else False,
                },
            )
            print(f"  updated {rtype} {name} -> {content} proxied={proxied}")
            return
    cf(
        "POST",
        f"/zones/{zone_id}/dns_records",
        token,
        {
            "type": rtype,
            "name": name,
            "content": content,
            "ttl": 1,
            "proxied": proxied if rtype in ("A", "AAAA", "CNAME") else False,
        },
    )
    print(f"  created {rtype} {name} -> {content} proxied={proxied}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    secrets = _read_file_secrets()
    token = secrets.get("CLOUDFLARE_API_TOKEN", "")
    account = secrets.get("CLOUDFLARE_ACCOUNT_ID", "")
    if not token:
        print("CLOUDFLARE_API_TOKEN fehlt in deploy.secrets.local")
        return 1

    verify = cf("GET", "/user/tokens/verify", token)
    if not verify.get("success"):
        print("Token ungültig")
        return 1
    print("Token OK")

    zones = cf("GET", f"/zones?name={DOMAIN}", token)
    results = zones.get("result") or []
    if results:
        zone = results[0]
        print(f"Zone existiert: {zone['id']} status={zone.get('status')}")
    else:
        if not account:
            print("CLOUDFLARE_ACCOUNT_ID fehlt — Zone anlegen braucht Account-ID")
            return 1
        print(f"Lege Zone an: {DOMAIN}")
        created = cf(
            "POST",
            "/zones",
            token,
            {"name": DOMAIN, "account": {"id": account}, "jump_start": False, "type": "full"},
        )
        if not created.get("success"):
            print(created)
            return 1
        zone = created["result"]
        print(f"Zone angelegt: {zone['id']}")

    zone_id = zone["id"]
    ns = zone.get("name_servers") or []
    print("Nameserver (bei IONOS eintragen):")
    for n in ns:
        print(f"  {n}")

    # Apex + www + wildcard + bekannte Subdomains
    # Proxy orange für Web; MX/TXT DNS-only
    records_a = [
        (DOMAIN, True),
        (f"www.{DOMAIN}", True),
        (f"*.{DOMAIN}", False),  # Free: Wildcard nicht proxied
        (f"cal.{DOMAIN}", True),
        (f"yassine.{DOMAIN}", True),
        (f"muster.{DOMAIN}", True),
        (f"voice.{DOMAIN}", True),
    ]
    print(f"\nDNS A-Records -> Origin {ORIGIN}")
    for name, proxied in records_a:
        ensure_record(token, zone_id, "A", name, ORIGIN, proxied=proxied)

    # Mail bei IONOS behalten
    print("\nMX / TXT (IONOS-Mail)")
    # Cloudflare MX needs priority — use raw API for priority
    def ensure_mx(name: str, content: str, priority: int) -> None:
        listed = cf("GET", f"/zones/{zone_id}/dns_records?type=MX&name={urllib.parse.quote(name)}", token)
        for rec in listed.get("result") or []:
            if rec.get("content") == content:
                cf(
                    "PUT",
                    f"/zones/{zone_id}/dns_records/{rec['id']}",
                    token,
                    {"type": "MX", "name": name, "content": content, "priority": priority, "ttl": 1},
                )
                print(f"  updated MX {content} prio={priority}")
                return
        cf(
            "POST",
            f"/zones/{zone_id}/dns_records",
            token,
            {"type": "MX", "name": name, "content": content, "priority": priority, "ttl": 1},
        )
        print(f"  created MX {content} prio={priority}")

    ensure_mx(DOMAIN, "mx00.ionos.de", 10)
    ensure_mx(DOMAIN, "mx01.ionos.de", 10)

    def ensure_txt(name: str, content: str) -> None:
        listed = cf("GET", f"/zones/{zone_id}/dns_records?type=TXT&name={urllib.parse.quote(name)}", token)
        for rec in listed.get("result") or []:
            # Cloudflare may wrap TXT in quotes
            existing = (rec.get("content") or "").strip('"')
            if existing == content or rec.get("content") == content:
                print(f"  TXT existiert: {content[:50]}…")
                return
        cf(
            "POST",
            f"/zones/{zone_id}/dns_records",
            token,
            {"type": "TXT", "name": name, "content": content, "ttl": 1},
        )
        print(f"  created TXT {content[:60]}")

    ensure_txt(DOMAIN, "v=spf1 include:_spf-eu.ionos.com ~all")
    ensure_txt(DOMAIN, "google-site-verification=QBC43NryOl8OFr0euty6qS2FIcY7I8ubOnK8Gya311E")
    # replit-verify weglassen (veraltet)

    # SSL mode Full (strict) empfohlen wenn Origin Let's Encrypt hat
    cf(
        "PATCH",
        f"/zones/{zone_id}/settings/ssl",
        token,
        {"value": "full"},
    )
    print("\nSSL mode: full")

    print("\n=== NÄCHSTER SCHRITT (Christian bei IONOS) ===")
    print(f"Domain {DOMAIN} → DNS → Nameserver ändern auf:")
    for n in ns:
        print(f"  {n}")
    print("MX/Mail-Records: falls Postfach bei IONOS, MX in Cloudflare nachtragen (DNS only).")
    print("Propagation: oft 1–24 Std. Status in Cloudflare bis 'Active'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
