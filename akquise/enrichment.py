"""Website & signal enrichment for Akquise-Krieger."""
from __future__ import annotations

import re
import time
from urllib.parse import urljoin, urlparse

import requests

from openness import scan_culture_signals

PHONE_RE = re.compile(
    r"(?:\+49|0049|0)\s*[\d\s\-/()]{8,18}\d"
)
LEGAL_RE = re.compile(
    r"\b(GmbH|UG\s*\(haftungsbeschränkt\)|UG|e\.?\s*K\.?|GbR|OHG|Einzelunternehmen)\b",
    re.I,
)
OWNER_PATTERNS = [
    re.compile(r"(?:geschäftsführer|geschaeftsfuehrer|inhaber|verantwortlich(?:er)?)\s*[:\s]+([A-ZÄÖÜ][a-zäöüß\-]+(?:\s+[A-ZÄÖÜ][a-zäöüß\-]+){0,3})", re.I),
    re.compile(r"([A-ZÄÖÜ][a-zäöüß\-]+(?:\s+[A-ZÄÖÜ][a-zäöüß\-]+){1,2})\s*[,]?\s*(?:geschäftsführer|inhaber)", re.I),
]
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if not url.startswith("http"):
        url = "https://" + url
    return url.split("#")[0].rstrip("/")


def empty_signals(has_website: bool = False) -> dict:
    return {
        "has_website": has_website,
        "checked": False,
        "status_code": 0,
        "final_url": "",
        "load_time_ms": 0,
        "https": False,
        "mobile_viewport": False,
        "title": "",
        "delivery_platforms": [],
        "job_signals": [],
        "order_signals": [],
        "social": [],
        "cms": [],
        "google_maps_link": False,
        "email_found": [],
        "contact_person": "",
        "contact_emails": [],
        "contact_phones": [],
        "legal_form": "",
        "impressum_checked": False,
        "pdf_menu": False,
        "only_social_site": False,
        "subpages_checked": [],
        "providers": [],
        "tradition_signals": [],
        "succession_signals": [],
        "resistance_signals": [],
        "young_signals": [],
        "meta_ads_checked": False,
        "runs_facebook_ads": False,
        "meta_ads": {},
        "register_checked": False,
        "register": {},
        "error": "",
    }


def _detect_platforms(text: str, host: str, cfg: dict) -> list[str]:
    found: list[str] = []
    hay = text + " " + host
    for plat in cfg.get("delivery_platforms", []):
        if plat.replace(".", r"\.") in hay or plat in hay:
            if plat not in found:
                found.append(plat)
    extras = ["lieferservice", "bringdienst", "order.app", "gastroportal", "gastro-hero", "orderbird"]
    for ex in extras:
        if ex in hay and ex not in found:
            found.append(ex)
    return found


def _detect_jobs(text: str, cfg: dict) -> list[str]:
    return [kw for kw in cfg.get("job_keywords", []) if kw in text]


def _detect_order(text: str, cfg: dict) -> list[str]:
    return [kw for kw in cfg.get("order_keywords", []) if kw in text]


def _detect_social(text: str) -> list[str]:
    out = []
    for s in ("facebook.com", "instagram.com", "tiktok.com"):
        if s in text:
            out.append(s.split(".")[0])
    return out


def _detect_cms(text: str, host: str) -> list[str]:
    hay = text + host
    cms_map = {
        "wordpress": ("wp-content", "wordpress"),
        "wix": ("wix.com", "wixsite"),
        "jimdo": ("jimdo",),
        "ionos": ("ionos", "1and1"),
        "squarespace": ("squarespace",),
        "shopify": ("shopify", "cdn.shopify"),
    }
    found = []
    for name, markers in cms_map.items():
        if any(m in hay for m in markers):
            found.append(name)
    return found


def _extract_emails(html: str) -> list[str]:
    emails = set()
    for m in re.finditer(r'mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', html, re.I):
        emails.add(m.group(1).lower())
    for m in EMAIL_RE.finditer(html[:50000]):
        e = m.group(0).lower()
        if not e.endswith((".png", ".jpg", ".gif", ".webp")):
            emails.add(e)
    return sorted(emails)[:5]


def _extract_phones(text: str) -> list[str]:
    found = []
    for m in PHONE_RE.finditer(text[:30000]):
        p = re.sub(r"\s+", " ", m.group(0)).strip()
        if len(p) >= 10 and p not in found:
            found.append(p)
    return found[:3]


def _extract_owner(text: str) -> str:
    plain = re.sub(r"<[^>]+>", " ", text)
    plain = re.sub(r"\s+", " ", plain)
    for pat in OWNER_PATTERNS:
        m = pat.search(plain)
        if m:
            name = m.group(1).strip()
            if 4 < len(name) < 60:
                return name
    return ""


def _parse_impressum(html: str) -> dict:
    text = html
    plain = re.sub(r"<[^>]+>", " ", html)
    lf = LEGAL_RE.search(plain)
    return {
        "contact_person": _extract_owner(text),
        "contact_emails": _extract_emails(html),
        "contact_phones": _extract_phones(plain),
        "legal_form": lf.group(1) if lf else "",
        "impressum_checked": True,
    }


def _merge_impressum(sig: dict, imp: dict) -> None:
    if imp.get("contact_person") and not sig.get("contact_person"):
        sig["contact_person"] = imp["contact_person"]
    for e in imp.get("contact_emails", []):
        if e not in sig["contact_emails"]:
            sig["contact_emails"].append(e)
        if e not in sig["email_found"]:
            sig["email_found"].append(e)
    for p in imp.get("contact_phones", []):
        if p not in sig["contact_phones"]:
            sig["contact_phones"].append(p)
    if imp.get("legal_form"):
        sig["legal_form"] = imp["legal_form"]
    sig["impressum_checked"] = sig["impressum_checked"] or imp.get("impressum_checked", False)


def _parse_html_signals(html: str, url: str, cfg: dict) -> dict:
    text = html.lower()
    host = urlparse(url).netloc.lower()
    title_m = re.search(r"<title[^>]*>([^<]{1,120})", html, re.I | re.S)
    title = re.sub(r"\s+", " ", title_m.group(1)).strip() if title_m else ""
    viewport = 'name="viewport"' in text or "width=device-width" in text
    maps_link = "google.com/maps" in text or "maps.app.goo.gl" in text
    pdf_menu = ".pdf" in text and ("speisekarte" in text or "menu" in text)

    return {
        "title": title[:120],
        "mobile_viewport": viewport,
        "google_maps_link": maps_link,
        "pdf_menu": pdf_menu,
        "delivery_platforms": _detect_platforms(text, host, cfg),
        "job_signals": _detect_jobs(text, cfg),
        "order_signals": _detect_order(text, cfg),
        "social": _detect_social(text),
        "cms": _detect_cms(text, host),
        "email_found": _extract_emails(html),
    }


def _merge_signals(base: dict, extra: dict) -> None:
    for key in ("delivery_platforms", "job_signals", "order_signals", "social", "cms", "email_found", "contact_emails", "contact_phones", "tradition_signals", "succession_signals", "resistance_signals", "young_signals"):
        for item in extra.get(key, []):
            if item not in base[key]:
                base[key].append(item)
    for key in ("mobile_viewport", "google_maps_link", "pdf_menu"):
        base[key] = base[key] or extra.get(key, False)
    if extra.get("title") and not base.get("title"):
        base["title"] = extra["title"]


def crawl_website(lead: dict, cfg: dict, session: requests.Session | None = None) -> dict:
    url = normalize_url(lead.get("website", ""))
    sig = empty_signals(has_website=bool(url))
    if not url:
        return sig

    sess = session or requests.Session()
    timeout = cfg.get("crawl", {}).get("request_timeout", 14)
    max_bytes = cfg.get("crawl", {}).get("html_max_bytes", 150000)
    headers = {"User-Agent": cfg.get("user_agent", "Webschmiede-Akquise/1.0")}

    try:
        t0 = time.time()
        r = sess.get(url, timeout=timeout, headers=headers, allow_redirects=True)
        sig["checked"] = True
        sig["status_code"] = r.status_code
        sig["final_url"] = r.url
        sig["load_time_ms"] = int((time.time() - t0) * 1000)
        sig["https"] = r.url.startswith("https://")

        if r.status_code >= 400:
            sig["error"] = f"HTTP {r.status_code}"
            return sig

        html = (r.text or "")[:max_bytes]
        parsed = _parse_html_signals(html, r.url, cfg)
        _merge_signals(sig, parsed)

        culture = scan_culture_signals(html)
        for k, v in culture.items():
            sig[k] = v

        host = urlparse(r.url).netloc.lower()
        if "facebook.com" in host or "instagram.com" in host:
            sig["only_social_site"] = True

        # Impressum / Kontakt (Pflichtangaben DE)
        impressum_paths = cfg.get("impressum_paths", ["/impressum", "/imprint", "/legal", "/kontakt", "/contact"])
        for path in impressum_paths[:4]:
            imp_url = urljoin(r.url.rstrip("/") + "/", path.lstrip("/"))
            try:
                ir = sess.get(imp_url, timeout=8, headers=headers, allow_redirects=True)
                if ir.status_code < 400 and ir.text and len(ir.text) > 200:
                    if "impressum" in path or "imprint" in path or "legal" in path:
                        sig["subpages_checked"].append(path)
                    imp = _parse_impressum(ir.text[:max_bytes])
                    _merge_impressum(sig, imp)
                    if sig.get("contact_person") and sig.get("contact_emails"):
                        break
            except Exception:
                pass

        # Subpages (Karriere, Speisekarte, Bestellen)
        subpaths = cfg.get("subpages", ["/speisekarte", "/menu", "/bestellen", "/karriere", "/jobs", "/stellen"])
        max_sub = cfg.get("crawl", {}).get("max_subpages", 4)
        checked_sub = 0
        for path in subpaths:
            if checked_sub >= max_sub:
                break
            sub_url = urljoin(r.url.rstrip("/") + "/", path.lstrip("/"))
            if sub_url == r.url:
                continue
            try:
                sr = sess.get(sub_url, timeout=8, headers=headers, allow_redirects=True)
                if sr.status_code < 400 and sr.text:
                    sig["subpages_checked"].append(path)
                    sub_parsed = _parse_html_signals(sr.text[:max_bytes], sr.url, cfg)
                    _merge_signals(sig, sub_parsed)
                    cult = scan_culture_signals(sr.text[:max_bytes])
                    for k, v in cult.items():
                        for item in v:
                            if item not in sig.get(k, []):
                                sig.setdefault(k, []).append(item)
                    checked_sub += 1
            except Exception:
                pass

    except requests.Timeout:
        sig["error"] = "timeout"
    except Exception as e:
        sig["error"] = str(e)[:120]

    if sig.get("checked"):
        from providers import detect_providers
        blob = " ".join(
            filter(None, [
                sig.get("title", ""),
                " ".join(sig.get("delivery_platforms") or []),
                " ".join(sig.get("cms") or []),
                " ".join(sig.get("order_signals") or []),
                " ".join(sig.get("subpages_checked") or []),
            ])
        )
        host = urlparse(sig.get("final_url") or url).netloc
        sig["providers"] = detect_providers(blob, host, sig)

    return sig


def score_from_signals(lead: dict, sig: dict, cfg: dict | None = None) -> tuple[int, str, list[str]]:
    cfg = cfg or {}
    score = 0
    angles: list[str] = []
    amenity = lead.get("amenity", "")
    prio_types = cfg.get("priority_amenities") or ["restaurant", "fast_food"]

    if sig.get("delivery_platforms"):
        score += 50
        angles.append(f"Lieferdienst ({', '.join(sig['delivery_platforms'][:3])}), eigenes Portal ohne Provision")

    if not sig.get("has_website"):
        score += 40
        angles.append("Keine Website, Komplett-Paket Website + Bestellportal")
    elif sig.get("only_social_site"):
        score += 35
        angles.append("Nur Facebook/Instagram, professionelle Website + Bestellen")
    elif sig.get("status_code", 0) >= 400 or sig.get("error"):
        score += 30
        angles.append("Website offline/Fehler, Neustart mit Webschmiede-Stack")

    if sig.get("has_website") and not sig.get("https"):
        score += 12
        angles.append("Kein HTTPS, Vertrauen + Google-Ranking")

    if not sig.get("mobile_viewport") and sig.get("has_website") and sig.get("checked"):
        score += 15
        angles.append("Nicht mobil-optimiert, wichtig für Gäste am Handy")

    if sig.get("job_signals"):
        score += 28
        angles.append("Sucht Mitarbeiter, weniger Telefonstress durch Online-Bestellung + SMS-Link")

    if sig.get("order_signals") and not sig.get("delivery_platforms"):
        score += 8
        angles.append("Bestell-Hinweise da, eigenes System statt Drittanbieter")

    if not sig.get("order_signals") and sig.get("has_website") and sig.get("checked"):
        if not prio_types or amenity in prio_types or cfg.get("vertical") == "handwerk":
            score += 18
            label = "Kein Online-Bestellen" if cfg.get("vertical") == "gastro" else "Kein Online-Anfrage-System"
            angles.append(f"{label}, Umsatzpotenzial")

    if lead.get("phone"):
        score += 10

    if prio_types and amenity in prio_types:
        score += 8
    elif cfg.get("vertical") == "handwerk" and amenity:
        score += 5

    if sig.get("load_time_ms", 0) > 4000:
        score += 10
        angles.append("Langsame Website, schnelles Bestellportal")

    # Google Places enrichment
    gp = lead.get("google_places") or {}
    if gp.get("rating") and float(gp["rating"]) < 4.0 and gp.get("user_ratings_total", 0) > 5:
        score += 12
        angles.append(f"Google {gp['rating']}★, besserer Digital-Auftritt + Bewertungs-Funnel")

    if score >= 55 and (
        sig.get("delivery_platforms")
        or not sig.get("has_website")
        or sig.get("only_social_site")
        or (
            sig.get("checked")
            and not sig.get("order_signals")
            and (not prio_types or amenity in prio_types or cfg.get("vertical") == "handwerk")
        )
    ):
        priority = "high"
    elif score >= 32:
        priority = "medium"
    else:
        priority = "low"

    pitch = angles[0] if angles else (cfg.get("reference_client") or {}).get("pitch", "Digitaler Auftritt, Webschmiede")
    return score, priority, angles if angles else [pitch]
