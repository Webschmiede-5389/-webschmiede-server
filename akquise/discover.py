"""Discovery: Betriebe finden (Overpass, später Web-Suche)."""
from __future__ import annotations

import time

import requests


def build_overpass_query(cfg: dict, radius_m: int, lat: float, lon: float) -> str:
    disc = cfg.get("discovery") or {}
    parts = []

    amenities = disc.get("amenities") or cfg.get("amenities") or []
    if amenities:
        am = "|".join(amenities)
        parts.append(f'node["amenity"~"{am}"](around:{radius_m},{lat},{lon});')
        parts.append(f'way["amenity"~"{am}"](around:{radius_m},{lat},{lon});')

    crafts = disc.get("crafts") or []
    if crafts:
        cr = "|".join(crafts)
        parts.append(f'node["craft"~"{cr}"](around:{radius_m},{lat},{lon});')
        parts.append(f'way["craft"~"{cr}"](around:{radius_m},{lat},{lon});')

    shops = disc.get("shops") or []
    if shops:
        sh = "|".join(shops)
        parts.append(f'node["shop"~"{sh}"](around:{radius_m},{lat},{lon});')
        parts.append(f'way["shop"~"{sh}"](around:{radius_m},{lat},{lon});')

    offices = disc.get("office_tags") or []
    if offices:
        of = "|".join(offices)
        parts.append(f'node["office"~"{of}"](around:{radius_m},{lat},{lon});')
        parts.append(f'way["office"~"{of}"](around:{radius_m},{lat},{lon});')

    # Extra: Namenssuche (z. B. Trockenbau, die in OSM nicht als craft stehen)
    name_regex = (disc.get("name_regex") or "").strip()
    if name_regex:
        parts.append(f'node["name"~"{name_regex}",i](around:{radius_m},{lat},{lon});')
        parts.append(f'way["name"~"{name_regex}",i](around:{radius_m},{lat},{lon});')

    if not parts:
        raise ValueError("Vertical hat keine discovery-Regeln (amenities/crafts/shops)")

    body = "\n      ".join(parts)
    return f"""
    [out:json][timeout:180];
    (
      {body}
    );
    out center tags;
    """


def _passes_filters(row: dict, cfg: dict) -> bool:
    """name_hints: bei lauten Crafts (z. B. Maler) nur behalten wenn Name passt."""
    disc = cfg.get("discovery") or {}
    hints = [h.lower() for h in (disc.get("name_hints") or [])]
    noisy = set(disc.get("noisy_crafts") or [])
    if not hints or not noisy:
        return True
    craft = (row.get("amenity") or "").lower()
    if craft not in noisy:
        return True
    name = (row.get("name") or "").lower()
    return any(h in name for h in hints)


def parse_osm_element(el: dict) -> dict | None:
    tags = el.get("tags") or {}
    name = (tags.get("name") or tags.get("brand") or tags.get("operator") or "").strip()
    if not name or len(name) < 2:
        return None

    lat_e = el.get("lat") or (el.get("center") or {}).get("lat")
    lon_e = el.get("lon") or (el.get("center") or {}).get("lon")
    if lat_e is None or lon_e is None:
        return None

    city = tags.get("addr:city") or tags.get("addr:place") or ""
    street = tags.get("addr:street") or ""
    housenumber = tags.get("addr:housenumber") or ""
    postcode = tags.get("addr:postcode") or ""
    address = ", ".join(p for p in [f"{street} {housenumber}".strip(), postcode, city] if p)

    website = tags.get("website") or tags.get("contact:website") or ""
    facebook = tags.get("contact:facebook") or tags.get("facebook") or ""
    if not website and facebook:
        website = facebook

    biz_type = tags.get("amenity") or tags.get("craft") or tags.get("shop") or tags.get("office") or ""

    return {
        "name": name,
        "amenity": biz_type,
        "cuisine": tags.get("cuisine", ""),
        "description": tags.get("description", ""),
        "address": address,
        "phone": tags.get("phone") or tags.get("contact:phone") or "",
        "website": website if not website or website.startswith("http") else f"https://{website}",
        "email": tags.get("email") or tags.get("contact:email") or "",
        "lat": float(lat_e),
        "lon": float(lon_e),
        "osm_id": el.get("id"),
        "google_places": {},
        "signals": {},
        "score": 0,
        "priority": "low",
        "pitch_angle": "",
        "pitch_angles": [],
    }


def discover_overpass(cfg: dict, radius_km: float) -> list[dict]:
    """Ein oder mehrere Zentren (settings.centers), dedupliziert mergen."""
    centers = cfg.get("centers") or []
    if not centers and cfg.get("center"):
        centers = [cfg["center"]]
    if not centers:
        raise ValueError("Kein center/centers in settings")

    all_leads: list[dict] = []
    seen: set[str] = set()
    for center in centers:
        sub = dict(cfg)
        sub["center"] = center
        batch = _discover_one(sub, radius_km)
        for row in batch:
            key = f"{row['name'].lower()}|{round(row['lat'], 4)}|{round(row['lon'], 4)}"
            if key in seen:
                continue
            seen.add(key)
            row["discovery_center"] = center.get("name") or ""
            all_leads.append(row)
    return all_leads


def _discover_one(cfg: dict, radius_km: float) -> list[dict]:
    lat, lon = cfg["center"]["lat"], cfg["center"]["lon"]
    radius_m = int(radius_km * 1000)
    query = build_overpass_query(cfg, radius_m, lat, lon)
    ua = cfg.get("user_agent", "Webschmiede-Akquise/1.0")

    last_err: Exception | None = None
    for attempt in range(3):
        try:
            r = requests.post(
                "https://overpass-api.de/api/interpreter",
                data={"data": query},
                timeout=190,
                headers={"User-Agent": ua},
            )
            if r.status_code in (429, 502, 503, 504):
                last_err = requests.HTTPError(f"{r.status_code} Overpass busy")
                time.sleep(4 * (attempt + 1))
                continue
            r.raise_for_status()
            break
        except requests.RequestException as exc:
            last_err = exc
            time.sleep(4 * (attempt + 1))
    else:
        raise last_err or RuntimeError("Overpass discovery failed")

    leads: list[dict] = []
    seen: set[str] = set()
    for el in r.json().get("elements", []):
        row = parse_osm_element(el)
        if not row:
            continue
        if not _passes_filters(row, cfg):
            continue
        key = f"{row['name'].lower()}|{round(row['lat'], 4)}|{round(row['lon'], 4)}"
        if key in seen:
            continue
        seen.add(key)
        leads.append(row)
    return leads
