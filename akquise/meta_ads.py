"""Meta Ad Library · Werbe-Budget-Signal (optional Token)."""
from __future__ import annotations

import os
import re
import time
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parent.parent
SECRETS = ROOT / "deploy.secrets.local"


def load_meta_token() -> str | None:
    key = os.environ.get("META_AD_LIBRARY_TOKEN", "")
    if key:
        return key
    if SECRETS.exists():
        for line in SECRETS.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("META_AD_LIBRARY_TOKEN="):
                return line.split("=", 1)[1].strip()
    return None


def search_ads_api(business_name: str, token: str, country: str = "DE") -> dict:
    url = "https://graph.facebook.com/v21.0/ads_archive"
    params = {
        "search_terms": business_name,
        "ad_reached_countries": f'["{country}"]',
        "ad_active_status": "ALL",
        "limit": 5,
        "fields": "page_name,ad_creation_time,ad_delivery_start_time,ad_snapshot_url",
        "access_token": token,
    }
    try:
        r = requests.get(url, params=params, timeout=20)
        data = r.json()
        if "error" in data:
            return {"runs_ads": False, "error": data["error"].get("message", ""), "source": "api"}
        ads = data.get("data") or []
        return {
            "runs_ads": len(ads) > 0,
            "ad_count": len(ads),
            "page_name": ads[0].get("page_name") if ads else "",
            "source": "meta_api",
        }
    except requests.RequestException as e:
        return {"runs_ads": False, "error": str(e)[:80], "source": "api"}


def search_ads_public(business_name: str, country: str = "DE") -> dict:
    """Fallback ohne Token, öffentliche Ad-Library-Seite."""
    q = quote(business_name[:60])
    url = f"https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country={country}&q={q}&search_type=keyword_unordered"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; Webschmiede-Akquise/1.0)"}
    try:
        r = requests.get(url, timeout=18, headers=headers)
        text = r.text
        # Heuristik: Ergebnisse vs. leer
        if "No ads match" in text or "Keine Anzeigen" in text:
            return {"runs_ads": False, "ad_count": 0, "source": "public_html"}
        count = len(re.findall(r"data-testid=\"ad-card", text))
        if not count:
            count = len(re.findall(r"Library ID", text))
        return {
            "runs_ads": count > 0,
            "ad_count": min(count, 20),
            "source": "public_html",
            "library_url": url,
        }
    except requests.RequestException as e:
        return {"runs_ads": False, "error": str(e)[:80], "source": "public_html"}


def check_lead_ads(lead: dict, token: str | None = None) -> dict:
    name = lead.get("name") or ""
    if not name:
        return {"runs_ads": False}
    if token:
        result = search_ads_api(name, token)
        if result.get("runs_ads") or not result.get("error"):
            return result
    return search_ads_public(name)


def enrich_leads_ads(leads: list[dict], cfg: dict, *, max_checks: int = 40) -> int:
    if not cfg.get("meta_ads", {}).get("enabled", True):
        return 0
    token = load_meta_token()
    # Priorität: Budget A/B Kandidaten + Facebook-URL
    priority = sorted(
        leads,
        key=lambda l: (
            0 if "facebook" in (l.get("website") or "").lower() else 1,
            -l.get("score", 0),
        ),
    )
    checked = 0
    for lead in priority[:max_checks]:
        sig = lead.setdefault("signals", {})
        if sig.get("meta_ads_checked"):
            continue
        ads = check_lead_ads(lead, token)
        sig["meta_ads"] = ads
        sig["meta_ads_checked"] = True
        sig["runs_facebook_ads"] = ads.get("runs_ads", False)
        checked += 1
        time.sleep(0.35 if not token else 0.15)
    return checked
