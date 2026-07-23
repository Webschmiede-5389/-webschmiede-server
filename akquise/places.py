"""Google Places: Nearby + Find Place + Details pro Lead."""
from __future__ import annotations

import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
SECRETS = ROOT / "deploy.secrets.local"

DETAIL_FIELDS = (
    "place_id,name,rating,user_ratings_total,business_status,"
    "formatted_phone_number,website,url,opening_hours,reviews,"
    "price_level,types,vicinity"
)


def load_api_key() -> str | None:
    key = os.environ.get("GOOGLE_PLACES_API_KEY", "")
    if key:
        return key
    if SECRETS.exists():
        for line in SECRETS.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("GOOGLE_PLACES_API_KEY="):
                return line.split("=", 1)[1].strip()
    return None


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def fetch_nearby_places(
    lat: float,
    lon: float,
    radius_m: int,
    api_key: str,
    place_type: str = "restaurant",
) -> list[dict]:
    out: list[dict] = []
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params: dict = {
        "location": f"{lat},{lon}",
        "radius": min(radius_m, 50000),
        "type": place_type,
        "key": api_key,
    }
    for _ in range(3):
        r = requests.get(url, params=params, timeout=30)
        data = r.json()
        st = data.get("status")
        if st not in ("OK", "ZERO_RESULTS"):
            print(f"  Google Places nearby: {st}")
            break
        for p in data.get("results", []):
            out.append(_pack_place(p))
        token = data.get("next_page_token")
        if not token:
            break
        time.sleep(2.2)
        params = {"pagetoken": token, "key": api_key}
    return out


def find_place(query: str, api_key: str) -> dict | None:
    url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
    params = {
        "input": query,
        "inputtype": "textquery",
        "fields": "place_id,name,rating,user_ratings_total,business_status,formatted_address",
        "key": api_key,
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        if data.get("status") != "OK" or not data.get("candidates"):
            return None
        return _pack_place(data["candidates"][0])
    except requests.RequestException:
        return None


def fetch_place_details(place_id: str, api_key: str) -> dict:
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {"place_id": place_id, "fields": DETAIL_FIELDS, "language": "de", "key": api_key}
    try:
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        if data.get("status") != "OK":
            return {}
        return _pack_place(data.get("result", {}), detailed=True)
    except requests.RequestException:
        return {}


def _pack_place(p: dict, detailed: bool = False) -> dict:
    oh = p.get("opening_hours") or {}
    reviews = p.get("reviews") or []
    recent = reviews[0].get("text", "")[:120] if reviews else ""
    return {
        "place_id": p.get("place_id"),
        "name": p.get("name"),
        "rating": p.get("rating"),
        "user_ratings_total": p.get("user_ratings_total", 0),
        "business_status": p.get("business_status"),
        "vicinity": p.get("vicinity") or p.get("formatted_address", ""),
        "phone": p.get("formatted_phone_number", ""),
        "website": p.get("website", ""),
        "maps_url": p.get("url", ""),
        "price_level": p.get("price_level"),
        "types": p.get("types") or [],
        "open_now": oh.get("open_now"),
        "opening_hours": oh.get("weekday_text") or [],
        "recent_review_snippet": recent,
        "photo_count_est": len(p.get("photos") or []) if detailed else 0,
    }


def merge_places_into_leads(leads: list[dict], places: list[dict]) -> int:
    by_name: dict[str, dict] = {}
    for p in places:
        key = _norm(p.get("name") or "")
        if key and key not in by_name:
            by_name[key] = p
    merged = 0
    for lead in leads:
        key = _norm(lead.get("name") or "")
        if key in by_name:
            lead["google_places"] = {**by_name[key], **(lead.get("google_places") or {})}
            merged += 1
    return merged


def enrich_leads_places(leads: list[dict], api_key: str, *, details: bool = True, workers: int = 4) -> int:
    """Find Place für unmatched + optional Details."""
    enriched = 0

    def job(lead: dict):
        gp = lead.get("google_places") or {}
        if gp.get("place_id") and gp.get("user_ratings_total"):
            if details and not gp.get("website"):
                det = fetch_place_details(gp["place_id"], api_key)
                if det:
                    lead["google_places"] = {**gp, **det}
            return bool(lead.get("google_places"))

        city = ""
        if lead.get("address"):
            parts = lead["address"].split(",")
            city = parts[-1].strip() if parts else ""
        query = f"{lead.get('name', '')} {city}".strip()
        found = find_place(query, api_key)
        if not found:
            return False
        if details and found.get("place_id"):
            det = fetch_place_details(found["place_id"], api_key)
            found = {**found, **det}
        lead["google_places"] = found
        if found.get("phone") and not lead.get("phone"):
            lead["phone"] = found["phone"]
        if found.get("website") and not lead.get("website"):
            lead["website"] = found["website"]
        return True

    unmatched = [l for l in leads if not (l.get("google_places") or {}).get("user_ratings_total")]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(job, l): l for l in unmatched[:120]}
        for fut in as_completed(futs):
            if fut.result():
                enriched += 1
            time.sleep(0.05)

    if details:
        with_details = [l for l in leads if (l.get("google_places") or {}).get("place_id") and not (l.get("google_places") or {}).get("website")]
        for lead in with_details[:80]:
            pid = lead["google_places"]["place_id"]
            det = fetch_place_details(pid, api_key)
            if det:
                lead["google_places"] = {**lead["google_places"], **det}
                enriched += 1
            time.sleep(0.08)

    return enriched + sum(1 for l in leads if l.get("google_places"))


fetch_nearby_restaurants = fetch_nearby_places
