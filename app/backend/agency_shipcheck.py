"""Freigabe-Check (Shipcheck): Links/Dashboards prüfen bevor Christian sie sieht.

Kein Auto-Send. Rot = nicht schicken. Grün = freigeben.
"""
from __future__ import annotations

import json
import re
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.I)

# Bekannte Agency-/Kunden-Surfaces → Extra-Checks
KNOWN = {
    "digitalehandwerkskunst.de/agency-setup": {"kind": "dashboard", "expect": [200]},
    "digitalehandwerkskunst.de/b2b-portal": {"kind": "dashboard", "expect": [200]},
    "digitalehandwerkskunst.de/buchhaltung-onboarding": {"kind": "dashboard", "expect": [200]},
    "digitalehandwerkskunst.de/api/health": {"kind": "api", "expect": [200], "json_ok": True},
    "digitalehandwerkskunst.de/nils": {"kind": "dashboard", "expect": [200, 401, 403]},
    "snackhouse-yassine.de": {"kind": "customer", "expect": [200, 301, 302]},
    "yassine.digitalehandwerkskunst.de": {"kind": "customer", "expect": [200, 301, 302]},
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def extract_urls(text: str) -> list[str]:
    found = URL_RE.findall(text or "")
    out: list[str] = []
    seen: set[str] = set()
    for u in found:
        u = u.rstrip(".,;:!?)>]}")
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _probe(url: str, timeout: int = 15) -> dict[str, Any]:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "WebschmiedeShipcheck/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            body = r.read(24000)
            code = getattr(r, "status", None) or r.getcode()
            final = r.geturl()
            ctype = r.headers.get("Content-Type", "")
            text = body.decode("utf-8", errors="replace")
            return {
                "ok_http": 200 <= int(code) < 400,
                "status": int(code),
                "final_url": final,
                "content_type": ctype,
                "bytes": len(body),
                "body": text,
                "snippet": text[:120],
                "error": None,
            }
    except urllib.error.HTTPError as e:
        return {
            "ok_http": False,
            "status": int(e.code),
            "final_url": url,
            "content_type": "",
            "bytes": 0,
            "body": "",
            "snippet": "",
            "error": f"HTTP {e.code}",
        }
    except Exception as e:
        return {
            "ok_http": False,
            "status": 0,
            "final_url": url,
            "content_type": "",
            "bytes": 0,
            "body": "",
            "snippet": "",
            "error": str(e)[:160],
        }


def _looks_soft_404(url: str, body: str, status: int) -> str | None:
    """Nginx/SPA oft 200 statt 404 – grob erkennen."""
    if status != 200 or not body:
        return None
    low = body.lower()
    # Nur klare Fehlerseiten, nicht JS-Strings in Apps
    if any(x in low for x in ("404 not found", "seite nicht gefunden", "page not found")):
        return "Soft-404 im HTML"
    if "<title>404" in low or "error 404" in low:
        return "Soft-404 im HTML"
    host = (urlparse(url).hostname or "").lower()
    path = (urlparse(url).path or "/").rstrip("/") or "/"
    if host.endswith("digitalehandwerkskunst.de") and path not in ("/", ""):
        # Unbekannter Pfad und Body ist nur die Root-SPA/Index → verdächtig
        known_hit = any(k in url.lower() for k in KNOWN)
        if not known_hit and ("<title>" in low):
            # Root zum Vergleich
            root = f"https://{host}/"
            if url.rstrip("/") != root.rstrip("/"):
                root_probe = _probe(root)
                root_body = root_probe.get("body") or ""
                if root_body and body[:2000] == root_body[:2000]:
                    return "Soft-404: gleiche Seite wie Startseite"
                # Leerer/kurzer Catch-all ohne echten Inhalt
                if len(body) < 400 and "webschmiede" not in low:
                    return "Verdächtig kurze Antwort für Dashboard-Pfad"
    return None


def _match_known(url: str) -> dict[str, Any] | None:
    low = url.lower()
    for key, meta in KNOWN.items():
        if key in low:
            return meta
    return None


def check_url(url: str) -> dict[str, Any]:
    probe = _probe(url)
    known = _match_known(url)
    expect = (known or {}).get("expect") or [200, 301, 302]
    status = probe.get("status") or 0
    status_ok = status in expect or (200 <= status < 400 and not known)
    issues: list[str] = []
    if probe.get("error") and not status_ok:
        issues.append(probe["error"])
    if status and status not in expect and known:
        issues.append(f"Status {status}, erwartet {expect}")
    if status == 404:
        issues.append("404 – Link tot oder falscher Pfad")
    if status >= 500:
        issues.append("Serverfehler 5xx")
    soft = _looks_soft_404(url, probe.get("body") or "", status)
    if soft:
        issues.append(soft)
        status_ok = False
    # localhost / interne IPs nicht an Christian schicken
    host = urlparse(url).hostname or ""
    if host in ("localhost", "127.0.0.1") or host.startswith("192.168.") or host.startswith("10."):
        issues.append("Interner Host – nicht an Kunden/Christian als Live-Link")
        status_ok = False
    if "digitalehandwerkskunst.de/api/" in url.lower() and status == 401:
        # Auth-APIs: 401 = erreichbar
        status_ok = True
        issues = [i for i in issues if "Status" not in i and "Soft-404" not in i]
    ok = status_ok and not any(
        x in i for i in issues for x in ("Interner", "404", "5xx", "Soft-404", "Verdächtig")
    )
    return {
        "url": url,
        "ok": ok,
        "status": status,
        "kind": (known or {}).get("kind") or "link",
        "issues": issues,
        "final_url": probe.get("final_url"),
        "content_type": probe.get("content_type"),
    }


def check_text(text: str, *, urls: list[str] | None = None) -> dict[str, Any]:
    """Prüft alle URLs in Text oder explizite Liste."""
    urls = list(urls or []) or extract_urls(text)
    if not urls:
        return {
            "ok": False,
            "ship": False,
            "agent": "shipcheck",
            "error": "Keine URL gefunden – zum Prüfen Link(s) mitgeben",
            "checks": [],
            "as_of": _now(),
        }
    checks = [check_url(u) for u in urls[:20]]
    failed = [c for c in checks if not c.get("ok")]
    ship = len(failed) == 0
    lines = [
        f"# Freigabe-Check {_now()}",
        f"Ergebnis: {'FREIGABE OK' if ship else 'NICHT SCHICKEN'}",
        f"Links: {len(checks)} · Fehler: {len(failed)}",
        "",
    ]
    for c in checks:
        mark = "OK" if c.get("ok") else "FAIL"
        iss = "; ".join(c.get("issues") or []) or "–"
        lines.append(f"- [{mark}] {c.get('status')} {c.get('url')} ({iss})")
    if not ship:
        lines += [
            "",
            "## Pflicht",
            "Links/Dashboards erst reparieren, dann erneut `shipcheck`.",
            "Christian bekommt keine toten Links.",
        ]
    else:
        lines += ["", "## Freigabe", "Alles erreichbar. Darf an Christian / Kunde."]
    return {
        "ok": True,
        "ship": ship,
        "agent": "shipcheck",
        "workflow": 15,
        "count": len(checks),
        "failed": len(failed),
        "checks": checks,
        "summary": "FREIGABE OK" if ship else "NICHT SCHICKEN",
        "markdown": "\n".join(lines),
        "as_of": _now(),
        "rule": "Keine Links an Christian ohne ship=true.",
    }


def check_dashboard(name: str) -> dict[str, Any]:
    """Bekannte Surfaces per Kurzname."""
    catalog = {
        "agency-setup": "https://digitalehandwerkskunst.de/agency-setup",
        "b2b": "https://digitalehandwerkskunst.de/b2b-portal.html",
        "buchhaltung-onboarding": "https://digitalehandwerkskunst.de/buchhaltung-onboarding.html",
        "sales-dashboard": "https://digitalehandwerkskunst.de/sales-dashboard.html",
        "sales-angebot": "https://digitalehandwerkskunst.de/sales-angebot.html",
        "health": "https://digitalehandwerkskunst.de/api/health",
        "yassine": "https://yassine.digitalehandwerkskunst.de/",
        "yassine-bestellen": "https://yassine.digitalehandwerkskunst.de/bestellen",
        "whatsapp-webhook": "https://digitalehandwerkskunst.de/api/whatsapp/webhook",
        "telegram-webhook": "https://digitalehandwerkskunst.de/api/telegram/webhook",
    }
    key = (name or "").strip().lower()
    if key not in catalog:
        return {
            "ok": False,
            "ship": False,
            "error": f"Unbekanntes Dashboard. Bekannt: {', '.join(catalog)}",
            "agent": "shipcheck",
        }
    return check_text("", urls=[catalog[key]])


def gate_before_share(text: str) -> dict[str, Any]:
    """Für Agenten: Text mit Links → nur freigeben wenn ship."""
    urls = extract_urls(text)
    if not urls:
        return {
            "ok": True,
            "ship": True,
            "skipped": True,
            "note": "Keine Links – Gate nicht nötig",
            "agent": "shipcheck",
        }
    result = check_text(text, urls=urls)
    result["skipped"] = False
    return result
