# Akquise-Krieger Gastro v2

Vollständiger Lead-Scan: OSM + **alle Websites** + Unterseiten + optional Google Places.

## Branchen

`gastro`, `handwerk`, `dach`, `trockenbau`, `elektro`, `friseur`, `dental`

Vollplan: [`krieger.md`](krieger.md)  
Verwandt (Wholesale/Multichannel): [`../b2b-euro-trading/README.md`](../b2b-euro-trading/README.md)

## Signale (pro Betrieb)

| Kategorie | Was erkannt wird |
|-----------|------------------|
| Lieferdienst | Lieferando, Wolt, Uber Eats, Takeaway, … |
| Bestellen | online bestellen, Speisekarte, Lieferservice, … |
| Personal | Jobs, Karriere, „wir suchen“, … |
| Technik | HTTPS, mobil, Ladezeit, CMS (WordPress, Wix, …) |
| Social | nur Facebook/Instagram als „Website“ |
| Unterseiten | /speisekarte, /menu, /bestellen, /karriere, … |
| Google | Bewertung + Anzahl (mit API-Key) |

## Output

- `docs/akquise/reports/DATUM-gastro.html` — Filter HIGH/MEDIUM
- `docs/akquise/reports/DATUM-gastro.json` — CRM-Import später
- `app/static/akquise-report.html` — für Deploy
- Live: http://167.233.211.170/akquise (nach setup_akquise.py)

## Google Places (optional)

In `deploy.secrets.local`:

```
GOOGLE_PLACES_API_KEY=AIza...
```

Places API in Google Cloud aktivieren (Nearby Search). Ohne Key: OSM + Crawl laufen trotzdem.

## Nacht-Cron (Server)

Täglich 02:00 — Log: `/var/log/akquise.log`

## Rechtliches

Öffentliche Daten only. **Kein Auto-Versand** an Betriebe (UWG). Du kontaktierst freigegebene Leads selbst.
