#!/usr/bin/env python3
"""Google Places API-Key testen (lokal oder Server)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "akquise"))

from places import fetch_nearby_places, find_place, load_api_key, fetch_place_details


def main() -> int:
    key = load_api_key()
    if not key:
        print("FEHLER: Kein Key in deploy.secrets.local")
        print("  Zeile: GOOGLE_PLACES_API_KEY=AIza...")
        return 1

    masked = key[:8] + "..." + key[-4:] if len(key) > 12 else "(zu kurz)"
    print(f"Key gefunden: {masked}")

    # Test 1: Nearby Search (Mechernich)
    places = fetch_nearby_places(50.5997, 6.6500, 3000, key, place_type="restaurant")
    if not places:
        print("FEHLER: Nearby Search — 0 Ergebnisse oder API blockiert")
        print("  → Places API in Cloud Console aktivieren?")
        print("  → Billing aktiviert?")
        return 1
    print(f"OK Nearby Search: {len(places)} Restaurants in 3 km")

    # Test 2: Find Place
    found = find_place("Snack House Mechernich", key)
    if not found:
        print("WARNUNG: Find Place — kein Treffer (optional)")
    else:
        print(f"OK Find Place: {found.get('name')} — {found.get('user_ratings_total', 0)} Bewertungen")

    # Test 3: Details
    if found and found.get("place_id"):
        det = fetch_place_details(found["place_id"], key)
        if det.get("website") or det.get("phone"):
            print(f"OK Details: Tel={det.get('phone','—')[:20]} Web={bool(det.get('website'))}")
        else:
            print("OK Details (ohne Tel/Web im Eintrag)")

    print("\nAlles bereit. Nächster Scan nutzt Google automatisch.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
