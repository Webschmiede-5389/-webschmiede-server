"""Cloudflare Schutz-Profil (WAF-ähnlich) für Agency- und Kunden-Domains."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


API = "https://api.cloudflare.com/client/v4"


def _secrets() -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        from agency_mail import _read_secrets

        out.update(_read_secrets())
    except Exception:
        pass
    for root in (Path("/root/app"), Path(__file__).resolve().parents[3]):
        for name in ("deploy.secrets.local",):
            path = root / name
            if not path.is_file():
                continue
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                s = line.strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                k, v = s.split("=", 1)
                out.setdefault(k.strip(), v.strip())
    for k in ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID"):
        if os.getenv(k):
            out[k] = os.getenv(k, "")
    return out


def token(secrets: dict | None = None) -> str:
    sec = secrets if secrets is not None else _secrets()
    return (sec.get("CLOUDFLARE_API_TOKEN") or "").strip()


def account_id(secrets: dict | None = None) -> str:
    sec = secrets if secrets is not None else _secrets()
    return (sec.get("CLOUDFLARE_ACCOUNT_ID") or "").strip()


def cf(method: str, path: str, tok: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {tok}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8", "replace") or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except Exception:
            parsed = {"raw": raw[:400]}
        return {"success": False, "http": e.code, "errors": parsed}


def find_zone(domain: str, tok: str | None = None) -> dict | None:
    t = tok or token()
    if not t:
        return None
    data = cf("GET", f"/zones?name={urllib.parse.quote(domain)}", t)
    results = data.get("result") or []
    return results[0] if results else None


def ensure_zone(domain: str, *, secrets: dict | None = None) -> dict:
    sec = secrets if secrets is not None else _secrets()
    t = token(sec)
    if not t:
        return {"ok": False, "error": "CLOUDFLARE_API_TOKEN fehlt"}
    existing = find_zone(domain, t)
    if existing:
        return {
            "ok": True,
            "zone_id": existing["id"],
            "status": existing.get("status"),
            "name_servers": existing.get("name_servers") or [],
            "created": False,
        }
    acc = account_id(sec)
    if not acc:
        return {"ok": False, "error": "CLOUDFLARE_ACCOUNT_ID fehlt"}
    created = cf(
        "POST",
        "/zones",
        t,
        {"name": domain, "account": {"id": acc}, "jump_start": False, "type": "full"},
    )
    if not created.get("success"):
        return {"ok": False, "error": created.get("errors") or created}
    zone = created["result"]
    return {
        "ok": True,
        "zone_id": zone["id"],
        "status": zone.get("status"),
        "name_servers": zone.get("name_servers") or [],
        "created": True,
    }


def ensure_a_record(
    zone_id: str,
    name: str,
    ip: str,
    *,
    proxied: bool = True,
    tok: str | None = None,
) -> None:
    t = tok or token()
    q = urllib.parse.quote(name)
    listed = cf("GET", f"/zones/{zone_id}/dns_records?type=A&name={q}", t)
    body = {"type": "A", "name": name, "content": ip, "ttl": 1, "proxied": proxied}
    for rec in listed.get("result") or []:
        cf("PUT", f"/zones/{zone_id}/dns_records/{rec['id']}", t, body)
        return
    cf("POST", f"/zones/{zone_id}/dns_records", t, body)


def apply_protection_profile(zone_id: str, *, tok: str | None = None) -> dict[str, Any]:
    """Security-Einstellungen wie bei SaaS-Portalen (Free-Plan-tauglich)."""
    t = tok or token()
    results: dict[str, Any] = {}

    settings = [
        ("ssl", {"value": "full"}),  # full_strict wenn Origin immer gültiges LE hat
        ("always_use_https", {"value": "on"}),
        ("min_tls_version", {"value": "1.2"}),
        ("automatic_https_rewrites", {"value": "on"}),
        ("security_level", {"value": "medium"}),
        ("browser_check", {"value": "on"}),
        ("email_obfuscation", {"value": "on"}),
        ("server_side_exclude", {"value": "on"}),
        ("hotlink_protection", {"value": "off"}),  # Logos/QR dürfen fremd geladen werden
        ("ip_geolocation", {"value": "on"}),
        ("challenge_ttl", {"value": 1800}),
    ]
    for key, body in settings:
        resp = cf("PATCH", f"/zones/{zone_id}/settings/{key}", t, body)
        results[key] = bool(resp.get("success")) or resp.get("http")

    # Bot Fight: Free-Plan oft nur im Dashboard; API-Setting heißt je nach Account anders
    for bot_key in ("bot_fight_mode", "botnet_fight_mode"):
        bot = cf("PATCH", f"/zones/{zone_id}/settings/{bot_key}", t, {"value": "on"})
        if bot.get("success"):
            results["bot_fight_mode"] = True
            break
        results["bot_fight_mode"] = {
            "ok": False,
            "hint": "Im Cloudflare-Dashboard: Security → Bots → Bot Fight Mode an",
        }

    # Under Attack nur manuell; wir setzen nicht dauerhaft
    return {"ok": True, "settings": results}


def provision_customer_domain(
    domain: str,
    origin_ip: str,
    *,
    secrets: dict | None = None,
    with_www: bool = True,
) -> dict:
    """Zone + Proxied A-Records + Schutzprofil für eine Kunden-Domain."""
    domain = domain.lower().strip().rstrip(".")
    z = ensure_zone(domain, secrets=secrets)
    if not z.get("ok"):
        return z
    zone_id = z["zone_id"]
    t = token(secrets)
    ensure_a_record(zone_id, domain, origin_ip, proxied=True, tok=t)
    if with_www:
        ensure_a_record(zone_id, f"www.{domain}", origin_ip, proxied=True, tok=t)
    prot = apply_protection_profile(zone_id, tok=t)
    return {
        "ok": True,
        "domain": domain,
        "zone_id": zone_id,
        "status": z.get("status"),
        "name_servers": z.get("name_servers") or [],
        "proxied": True,
        "protection": prot,
        "next_step": "Nameserver beim Registrar auf die Cloudflare-NS setzen",
    }
