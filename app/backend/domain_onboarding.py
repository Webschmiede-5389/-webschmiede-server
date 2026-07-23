"""domain onboarding: availability, wish check, customer select."""
from __future__ import annotations

import json
import os
import re
import socket
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

KUNDEN_DIR = Path(os.getenv("KUNDEN_DIR", Path(__file__).resolve().parents[1] / "kunden"))

# Auto-Kauf nur mit explizitem Schalter (Standard: aus). Nie still kaufen.
AUTO_PURCHASE = os.getenv("DOMAIN_AUTO_PURCHASE", "").lower() in ("1", "true", "yes")

_DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)[a-z0-9-]+(?:\.[a-z0-9-]+)+$",
    re.IGNORECASE,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_kunde(kid: str) -> tuple[dict, Path] | None:
    kid = (kid or "").upper().strip()
    if not kid or not KUNDEN_DIR.is_dir():
        return None
    for p in KUNDEN_DIR.glob("*.json"):
        if p.name.startswith(kid):
            return json.loads(p.read_text(encoding="utf-8")), p
    return None


def _save_kunde(k: dict, path: Path) -> None:
    path.write_text(json.dumps(k, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _secrets() -> dict[str, str]:
    try:
        from agency_mail import _read_secrets

        return _read_secrets()
    except Exception:
        pass
    path = Path("/root/app/deploy.secrets.local")
    if not path.exists():
        path = Path(__file__).resolve().parents[2] / "deploy.secrets.local"
    out: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            key, val = s.split("=", 1)
            out[key.strip()] = val.strip()
    return out


def normalize_domain(raw: str) -> str:
    s = (raw or "").strip().lower()
    s = s.replace("https://", "").replace("http://", "")
    s = s.split("/")[0].split("?")[0].strip(".")
    if s.startswith("www."):
        s = s[4:]
    return s


def is_valid_domain(name: str) -> bool:
    return bool(name) and bool(_DOMAIN_RE.match(name)) and "." in name


def _http_json(method: str, url: str, *, headers: dict | None = None, body: dict | None = None, timeout: int = 18):
    data = None
    hdrs = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except Exception:
            parsed = {"raw": raw[:400]}
        return e.code, parsed
    except Exception as e:
        return None, {"error": str(e)[:200]}


def _dns_has_ns(domain: str) -> bool:
    try:
        socket.getaddrinfo(domain, None)
        return True
    except OSError:
        pass
    try:
        import subprocess

        r = subprocess.run(
            ["nslookup", "-type=NS", domain],
            capture_output=True,
            text=True,
            timeout=8,
        )
        out = (r.stdout or "") + (r.stderr or "")
        return "nameserver" in out.lower() and "can't find" not in out.lower()
    except Exception:
        return False


def _rdap_available(domain: str) -> tuple[bool | None, str]:
    """True=frei, False=belegt, None=unbekannt."""
    tld = domain.rsplit(".", 1)[-1]
    if tld == "de":
        status, _ = _http_json("GET", f"https://rdap.denic.de/domain/{domain}")
        if status == 404:
            return True, "rdap_denic"
        if status == 200:
            return False, "rdap_denic"
        return None, f"rdap_denic_http_{status}"
    if tld in ("com", "net"):
        status, _ = _http_json("GET", f"https://rdap.verisign.com/{tld}/v1/domain/{domain}")
        if status == 404:
            return True, "rdap_verisign"
        if status == 200:
            return False, "rdap_verisign"
        return None, f"rdap_verisign_http_{status}"
    if tld == "org":
        status, _ = _http_json("GET", f"https://rdap.publicinterestregistry.org/rdap/domain/{domain}")
        if status == 404:
            return True, "rdap_pir"
        if status == 200:
            return False, "rdap_pir"
        return None, f"rdap_pir_http_{status}"
    return None, "rdap_unsupported_tld"


def _cloudflare_check(domains: list[str]) -> dict[str, dict]:
    sec = _secrets()
    token = sec.get("CLOUDFLARE_API_TOKEN") or os.getenv("CLOUDFLARE_API_TOKEN", "")
    account = sec.get("CLOUDFLARE_ACCOUNT_ID") or os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
    if not token or not account or not domains:
        return {}
    status, data = _http_json(
        "POST",
        f"https://api.cloudflare.com/client/v4/accounts/{account}/registrar/domain-check",
        headers={"Authorization": f"Bearer {token}"},
        body={"domains": domains[:20]},
    )
    out: dict[str, dict] = {}
    if status != 200 or not data.get("success"):
        return out
    for row in (data.get("result") or {}).get("domains") or []:
        name = (row.get("name") or "").lower()
        if not name:
            continue
        out[name] = row
    return out


def check_domain(raw: str) -> dict:
    domain = normalize_domain(raw)
    if not is_valid_domain(domain):
        return {
            "domain": domain,
            "ok": False,
            "available": False,
            "status": "invalid",
            "message": "Bitte eine gültige Domain eingeben, z. B. snackhouse-yassine.de",
        }

    tld = domain.rsplit(".", 1)[-1]
    cf = _cloudflare_check([domain]).get(domain)
    if cf is not None:
        registrable = bool(cf.get("registrable"))
        reason = cf.get("reason") or ""
        pricing = cf.get("pricing") or {}
        if reason == "extension_not_supported" or reason == "extension_not_supported_via_api":
            # CF kennt TLD nicht / API nicht: RDAP fallback
            pass
        elif registrable:
            return {
                "domain": domain,
                "ok": True,
                "available": True,
                "status": "available",
                "source": "cloudflare",
                "tier": cf.get("tier"),
                "pricing": pricing,
                "can_auto_purchase": AUTO_PURCHASE and tld != "de",
                "message": f"{domain} ist frei.",
            }
        else:
            return {
                "domain": domain,
                "ok": True,
                "available": False,
                "status": "taken",
                "source": "cloudflare",
                "reason": reason or "domain_unavailable",
                "can_auto_purchase": False,
                "message": f"{domain} ist nicht frei.",
            }

    avail, source = _rdap_available(domain)
    if avail is True:
        return {
            "domain": domain,
            "ok": True,
            "available": True,
            "status": "available",
            "source": source,
            "can_auto_purchase": False,
            "message": f"{domain} scheint frei zu sein.",
            "note": "Kauf .de läuft über IONOS/INWX. Cloudflare kann .de nicht registrieren.",
        }
    if avail is False:
        return {
            "domain": domain,
            "ok": True,
            "available": False,
            "status": "taken",
            "source": source,
            "can_auto_purchase": False,
            "message": f"{domain} ist bereits vergeben.",
        }

    # letzter Hinweis: DNS
    if _dns_has_ns(domain):
        return {
            "domain": domain,
            "ok": True,
            "available": False,
            "status": "likely_taken",
            "source": "dns",
            "can_auto_purchase": False,
            "message": f"{domain} antwortet im DNS, vermutlich belegt.",
        }

    return {
        "domain": domain,
        "ok": True,
        "available": None,
        "status": "unknown",
        "source": source,
        "can_auto_purchase": False,
        "message": f"Für {domain} konnte die Verfügbarkeit nicht sicher geprüft werden.",
    }


def _slugify(text: str) -> str:
    s = (text or "").lower()
    repl = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}
    for a, b in repl.items():
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def _city_from_kunde(k: dict) -> str:
    addr = ((k.get("kontakt") or {}).get("adresse") or "")
    # "..., 53894 Mechernich" → Mechernich
    m = re.search(r"\b\d{5}\s+([A-Za-zÄÖÜäöüß\-]+)", addr)
    if m:
        return m.group(1)
    parts = [p.strip() for p in addr.split(",") if p.strip()]
    if parts:
        last = parts[-1]
        last = re.sub(r"^\d{5}\s*", "", last).strip()
        return last.split()[0] if last else ""
    return ""


def default_candidates(k: dict) -> list[str]:
    """Vorschläge erzeugen, wenn domain_options fehlt."""
    name = _slugify(k.get("name") or "")
    slug = _slugify(k.get("slug") or "")
    inhaber = _slugify(((k.get("inhaber") or "").split() or [""])[-1])
    city = _slugify(_city_from_kunde(k))
    brand = slug or name or "shop"
    # snackhouse-mechernich → snackhouse
    brand_short = brand.split("-")[0] if "-" in brand else brand

    cands: list[str] = []
    if brand_short and inhaber:
        cands.append(f"{brand_short}-{inhaber}.de")
    if brand_short and city:
        cands.append(f"{brand_short}-{city}.de")
        cands.append(f"{brand_short}{city}.de")
        cands.append(f"{city}-{brand_short}.de")
    if brand_short and inhaber and city:
        cands.append(f"{brand_short}-{inhaber}-{city}.de")
    if inhaber and city:
        cands.append(f"{inhaber}-{city}.de")
    if brand_short and inhaber:
        cands.append(f"{brand_short}-{inhaber}.com")

    # unique preserve order
    seen = set()
    out = []
    for d in cands:
        if d and d not in seen and is_valid_domain(d):
            seen.add(d)
            out.append(d)
    return out[:8]


def list_options(kid: str) -> dict:
    loaded = _load_kunde(kid)
    if not loaded:
        return {"ok": False, "error": "Kunde nicht gefunden"}
    k, _ = loaded
    dom = k.get("domain") or {}
    configured = list(dom.get("options") or k.get("domain_options") or [])
    if not configured:
        configured = default_candidates(k)

    # live status
    checks = []
    cf_map = _cloudflare_check(
        [normalize_domain(x) for x in configured if is_valid_domain(normalize_domain(x))]
    )
    for raw in configured:
        domain = normalize_domain(raw)
        if not is_valid_domain(domain):
            continue
        row = cf_map.get(domain)
        reason = (row or {}).get("reason") or ""
        # .de u. a.: CF sagt oft "nicht unterstützte Endung" → kein Belegt, RDAP nutzen
        if row is not None and reason not in (
            "extension_not_supported",
            "extension_not_supported_via_api",
            "extension_disallows_registration",
        ):
            available = bool(row.get("registrable"))
            item = {
                "domain": domain,
                "available": available,
                "status": "available" if available else "taken",
                "source": "cloudflare",
                "pricing": row.get("pricing"),
                "reason": reason or None,
                "message": f"{domain} ist frei." if available else f"{domain} ist nicht frei.",
            }
        else:
            item = check_domain(domain)
        checks.append(item)

    selected = (dom.get("selected") or "").strip().lower()
    return {
        "ok": True,
        "id": k.get("id"),
        "name": k.get("name"),
        "selected": selected,
        "status": dom.get("status") or ("live" if (k.get("urls") or {}).get("domain") else "open"),
        "wish": dom.get("wish") or "",
        "options": checks,
        "auto_purchase_enabled": AUTO_PURCHASE,
        "onboarding_url": (k.get("urls") or {}).get("onboarding_url") or "",
    }


def _owner_email() -> str:
    sec = _secrets()
    return (
        os.getenv("AGENCY_OWNER_EMAIL")
        or sec.get("AGENCY_OWNER_EMAIL")
        or sec.get("AGENCY_MAIL_BCC")
        or ""
    ).strip()


def _customer_email(k: dict) -> str:
    return ((k.get("kontakt") or {}).get("email") or "").strip()


def _send_mail(to: str, subject: str, html: str, text: str) -> bool:
    if not to:
        return False
    try:
        from agency_mail import send_html_email

        send_html_email(to=to, subject=subject, html=html, text=text)
        return True
    except Exception as e:
        print(f"[domain_onboarding] mail failed: {e}")
        return False


def _suggestions_after_taken(kid: str, taken: str, limit: int = 5) -> list[dict]:
    opts = list_options(kid)
    free = [o for o in (opts.get("options") or []) if o.get("available") is True and o.get("domain") != taken]
    if len(free) >= limit:
        return free[:limit]
    # extra candidates
    loaded = _load_kunde(kid)
    if not loaded:
        return free
    k, _ = loaded
    extras = []
    for d in default_candidates(k):
        if d == taken or any(x.get("domain") == d for x in free):
            continue
        c = check_domain(d)
        if c.get("available") is True:
            extras.append(c)
        if len(free) + len(extras) >= limit:
            break
    return (free + extras)[:limit]


def _mail_domain_taken(k: dict, wish: str, suggestions: list[dict]) -> dict:
    to = _customer_email(k)
    name = k.get("inhaber") or k.get("name") or ""
    shop = k.get("name") or ""
    onboarding = (k.get("urls") or {}).get("onboarding_url") or ""
    lines = [f"- {s['domain']}" for s in suggestions if s.get("domain")]
    suggest_txt = "\n".join(lines) if lines else "- (gerade keine freien Alternativen gefunden)"
    suggest_html = "".join(
        f"<li style=\"margin:6px 0;\"><strong>{s['domain']}</strong></li>" for s in suggestions if s.get("domain")
    ) or "<li>Gerade keine freien Alternativen gefunden.</li>"

    from email_templates import email_button, email_shell

    body = f"""
    <p style="margin:0 0 14px;color:#1A1A1A;font-size:15px;line-height:1.55;">
      Hallo {name},
    </p>
    <p style="margin:0 0 14px;color:#1A1A1A;font-size:15px;line-height:1.55;">
      Ihre Wunschdomain <strong>{wish}</strong> ist leider nicht frei.
    </p>
    <p style="margin:0 0 8px;color:#1A1A1A;font-size:15px;line-height:1.55;">
      Hier sind Alternativen, die gerade frei wirken:
    </p>
    <ul style="margin:0 0 18px;padding-left:20px;color:#1A1A1A;font-size:15px;">{suggest_html}</ul>
    <p style="margin:0 0 18px;color:#666;font-size:14px;line-height:1.5;">
      Im Onboarding können Sie eine Domain auswählen oder eine neue Wunschdomain prüfen.
    </p>
    {"<p style='margin:0 0 8px;'>" + email_button(onboarding, "Zur Domain-Auswahl") + "</p>" if onboarding else ""}
    """
    html = email_shell(
        hero_title="Domain nicht frei",
        hero_subtitle=shop,
        body_html=body,
        preheader=f"{wish} ist nicht frei",
    )
    text = (
        f"Hallo {name},\n\n"
        f"Ihre Wunschdomain {wish} ist leider nicht frei.\n\n"
        f"Alternativen:\n{suggest_txt}\n\n"
        f"{('Onboarding: ' + onboarding + chr(10)) if onboarding else ''}"
        f"Christian · Webschmiede\n"
    )
    sent = _send_mail(to, f"Domain nicht frei: {wish}", html, text)
    return {"sent": sent, "to": to}


def _mail_domain_selected(k: dict, domain: str, *, purchase: dict | None = None) -> dict:
    cust = _customer_email(k)
    owner = _owner_email()
    name = k.get("inhaber") or k.get("name") or ""
    shop = k.get("name") or ""
    kid = k.get("id") or ""
    purchase = purchase or {}
    purchase_note = purchase.get("message") or "Wir richten die Domain ein. Kauf erfolgt nach Freigabe bzw. manuell bei .de."

    from email_templates import email_shell

    body_c = f"""
    <p style="margin:0 0 14px;color:#1A1A1A;font-size:15px;line-height:1.55;">Hallo {name},</p>
    <p style="margin:0 0 14px;color:#1A1A1A;font-size:15px;line-height:1.55;">
      Danke. Sie haben <strong>{domain}</strong> gewählt.
    </p>
    <p style="margin:0 0 14px;color:#1A1A1A;font-size:15px;line-height:1.55;">
      {purchase_note}
    </p>
    <p style="margin:0;color:#666;font-size:14px;">Wir melden uns, sobald die Domain live ist.</p>
    """
    html_c = email_shell(
        hero_title="Domain gewählt",
        hero_subtitle=shop,
        body_html=body_c,
        preheader=f"Domain {domain} gewählt",
    )
    text_c = (
        f"Hallo {name},\n\nSie haben {domain} gewählt.\n{purchase_note}\n\n"
        f"Wir melden uns, sobald die Domain live ist.\n\nChristian · Webschmiede\n"
    )
    sent_c = _send_mail(cust, f"Domain gewählt: {domain}", html_c, text_c)

    body_o = f"""
    <p style="margin:0 0 14px;color:#1A1A1A;font-size:15px;line-height:1.55;">
      Kunde <strong>{shop}</strong> ({kid}) hat Domain <strong>{domain}</strong> gewählt.
    </p>
    <p style="margin:0 0 8px;color:#1A1A1A;font-size:15px;">Status Kauf: {purchase.get('status', 'pending')}</p>
    <p style="margin:0;color:#666;font-size:14px;">{purchase_note}</p>
    """
    html_o = email_shell(
        hero_title="Kunde Domain-Auswahl",
        hero_subtitle=f"{kid} · {shop}",
        body_html=body_o,
        preheader=f"{kid}: {domain}",
    )
    text_o = f"{kid} {shop}: Domain {domain} gewählt.\nKauf: {purchase.get('status')}\n{purchase_note}\n"
    sent_o = _send_mail(owner, f"[{kid}] Domain gewählt: {domain}", html_o, text_o) if owner else False
    return {"customer": {"sent": sent_c, "to": cust}, "owner": {"sent": sent_o, "to": owner}}


def check_wish(kid: str, raw: str) -> dict:
    loaded = _load_kunde(kid)
    if not loaded:
        return {"ok": False, "error": "Kunde nicht gefunden"}
    k, path = loaded
    result = check_domain(raw)
    if not result.get("ok") and result.get("status") == "invalid":
        return {"ok": False, **result}

    domain = result["domain"]
    k.setdefault("domain", {})
    k["domain"]["wish"] = domain
    k["domain"]["wish_checked_at"] = _now()
    k["domain"]["wish_status"] = result.get("status")
    _save_kunde(k, path)

    mail_info = {"sent": False}
    suggestions: list[dict] = []
    if result.get("available") is False:
        suggestions = _suggestions_after_taken(kid, domain)
        mail_info = _mail_domain_taken(k, domain, suggestions)
        k["domain"]["last_taken_mail_at"] = _now()
        _save_kunde(k, path)

    return {
        "ok": True,
        "check": result,
        "suggestions": suggestions,
        "mail": mail_info,
    }


def _try_purchase(domain: str) -> dict:
    """Kauf über INWX wenn konfiguriert. .de unterstützt. Sonst pending/manual."""
    sec = _secrets()
    origin = (
        sec.get("WEB_HOST")
        or os.getenv("WEB_HOST")
        or sec.get("SERVER_HOST")
        or ""
    ).strip()

    # INWX bevorzugen (inkl. .de)
    try:
        from integrations.inwx import InwxClient, purchase_and_point
    except ImportError:
        try:
            from app.backend.integrations.inwx import InwxClient, purchase_and_point  # type: ignore
        except ImportError:
            InwxClient = None  # type: ignore
            purchase_and_point = None  # type: ignore

    if InwxClient and purchase_and_point:
        client = InwxClient(secrets=sec)
        if client.configured():
            if not AUTO_PURCHASE:
                return {
                    "status": "pending_agency",
                    "message": (
                        f"Auswahl gespeichert. INWX ist bereit — Kauf mit DOMAIN_AUTO_PURCHASE=1 "
                        f"oder: python scripts/provision_domain_inwx.py {domain}"
                    ),
                    "provider": "inwx",
                    "origin": origin or None,
                }
            if not origin:
                return {
                    "status": "pending_agency",
                    "message": "WEB_HOST fehlt (Ziel-IP für A-Record).",
                    "provider": "inwx",
                }
            result = purchase_and_point(domain, origin, secrets=sec)
            result.setdefault("provider", "inwx")
            return result

    tld = domain.rsplit(".", 1)[-1]
    if tld == "de":
        return {
            "status": "manual_required",
            "message": (
                "Deutsche .de-Domains: INWX_USER/PASSWORD (+ CONTACT_ID) in Secrets setzen, "
                "dann Auto-Kauf oder scripts/provision_domain_inwx.py."
            ),
        }
    if not AUTO_PURCHASE:
        return {
            "status": "pending_agency",
            "message": "Auswahl gespeichert. Kauf startet erst nach Freigabe (kein Auto-Kauf aktiv).",
        }

    # Fallback Cloudflare (kein .de)
    token = sec.get("CLOUDFLARE_API_TOKEN") or ""
    account = sec.get("CLOUDFLARE_ACCOUNT_ID") or ""
    if not token or not account:
        return {"status": "pending_agency", "message": "Weder INWX noch Cloudflare Token. Auswahl gespeichert."}

    cf = _cloudflare_check([domain]).get(domain) or {}
    if not cf.get("registrable"):
        return {
            "status": "failed",
            "message": f"Domain {domain} ist bei Cloudflare nicht kaufbar ({cf.get('reason') or 'nicht frei'}).",
        }

    status, data = _http_json(
        "POST",
        f"https://api.cloudflare.com/client/v4/accounts/{account}/registrar/registrations",
        headers={"Authorization": f"Bearer {token}"},
        body={"domain_name": domain},
        timeout=30,
    )
    if status in (200, 201) and data.get("success"):
        return {
            "status": "purchased",
            "message": f"{domain} wurde bei Cloudflare registriert.",
            "result": data.get("result"),
            "provider": "cloudflare",
        }
    if status == 202 and data.get("success"):
        return {
            "status": "purchase_in_progress",
            "message": f"Registrierung von {domain} läuft.",
            "result": data.get("result"),
            "provider": "cloudflare",
        }
    err = (data.get("errors") or [{}])[0]
    return {
        "status": "failed",
        "message": err.get("message") or f"Kauf fehlgeschlagen (HTTP {status}).",
        "errors": data.get("errors"),
    }


def select_domain(kid: str, raw: str) -> dict:
    loaded = _load_kunde(kid)
    if not loaded:
        return {"ok": False, "error": "Kunde nicht gefunden"}
    k, path = loaded
    domain = normalize_domain(raw)
    if not is_valid_domain(domain):
        return {"ok": False, "error": "Ungültige Domain"}

    check = check_domain(domain)
    if check.get("available") is False:
        suggestions = _suggestions_after_taken(kid, domain)
        return {
            "ok": False,
            "error": f"{domain} ist nicht frei.",
            "check": check,
            "suggestions": suggestions,
        }

    purchase = _try_purchase(domain)

    k.setdefault("domain", {})
    k["domain"]["selected"] = domain
    k["domain"]["selected_at"] = _now()
    k["domain"]["status"] = purchase.get("status") or "pending_agency"
    k["domain"]["purchase"] = {
        "status": purchase.get("status"),
        "message": purchase.get("message"),
        "at": _now(),
    }
    # urls.domain erst setzen wenn wirklich live / gekauft – sonst nur selected
    if purchase.get("status") in ("purchased", "purchase_in_progress"):
        k.setdefault("urls", {})["domain"] = domain

    # history
    k.setdefault("agency_history", []).append(
        {
            "at": _now(),
            "action": "domain_selected",
            "detail": f"{domain} ({purchase.get('status')})",
        }
    )
    # offene Punkte anpassen
    pts = list(k.get("offene_punkte") or [])
    pts = [p for p in pts if "domain" not in p.lower()]
    if purchase.get("status") not in ("purchased",):
        pts.append(f"Domain {domain}: {purchase.get('status')}")
    k["offene_punkte"] = pts
    _save_kunde(k, path)

    mail = _mail_domain_selected(k, domain, purchase=purchase)
    return {
        "ok": True,
        "domain": domain,
        "check": check,
        "purchase": purchase,
        "mail": mail,
        "domain_state": k.get("domain"),
    }


def domain_payload_for_onboarding(kid: str) -> dict:
    """Leichtgewicht für GET /api/onboarding/<kid>."""
    data = list_options(kid)
    if not data.get("ok"):
        return {"ok": False, "options": [], "selected": "", "status": "open"}
    return {
        "ok": True,
        "selected": data.get("selected") or "",
        "status": data.get("status") or "open",
        "wish": data.get("wish") or "",
        "options": data.get("options") or [],
        "auto_purchase_enabled": data.get("auto_purchase_enabled"),
    }
