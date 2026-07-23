# Webschmiede Akquise Engine (Apify-ähnlich, self-hosted)

Eigene Lead-Engine statt Apify-Abos — **branchenunabhängig** über Vertical-Configs.

## Nicht 1:1 Apify — aber dieselbe Logik

| Apify | Unsere Engine |
|-------|----------------|
| Actors (Bots) | **Verticals** (`akquise/verticals/*.json`) |
| Input (Region, Branche) | `--vertical` + `--radius` + `settings.json` |
| Crawl / Scrape | Website + Impressum + Unterseiten |
| Dataset (JSON) | `docs/akquise/reports/DATUM-VERTICAL.json` |
| Schedule | Cron 02:00 auf Hetzner |
| Proxy-Rotation | ❌ Phase 2 (meist nicht nötig lokal) |
| Browser (Playwright) | ❌ Phase 2 (requests reicht für 90 %) |
| Actor Marketplace | Eigene Vertical-JSON anlegen |

## Befehle

```bash
python scripts/akquise_run.py --list
python scripts/akquise_run.py --vertical gastro --radius 25
python scripts/akquise_run.py --vertical handwerk --radius 30
```

Legacy: `python scripts/akquise_scan.py` (= gastro)

## Neue Branche anlegen (5 Min.)

1. `akquise/verticals/mein-vertical.json` kopieren (von `gastro.json` oder `handwerk.json`)
2. `discovery` anpassen (OSM-Tags: amenities, crafts, shops)
3. Keywords + `intents` anpassen
4. `python scripts/akquise_run.py --vertical mein-vertical`

## Architektur

```
Discover (OSM) → Crawl (Website/Impressum) → Enrich (Google optional)
    → Score → Intent → Report (HTML + JSON)
```

## Was die Engine pro Lead liefert

- Betrieb, Adresse, Telefon, Website
- Impressum: **Name, E-Mail, Tel, Rechtsform**
- Signale: Lieferdienst, Jobs, Bestellen, CMS, mobil, HTTPS
- **Kontakt-Spalte** + **Intention-Spalte** (rechts)
- Priorität HIGH / MEDIUM / LOW

## Grenzen (ehrlich)

- Kein LinkedIn-Scraping (rechtlich)
- Keine Apollo-Waterfall-Mails (US-DB)
- North Data / Apify API optional später anbindbar
- **Kontakt nur nach deiner Freigabe** (UWG)

## Dateien

| Pfad | Rolle |
|------|--------|
| `akquise/engine.py` | Pipeline |
| `akquise/discover.py` | OSM-Suche |
| `akquise/enrichment.py` | Website-Crawler |
| `akquise/intent.py` | Intention pro Vertical |
| `akquise/verticals/` | Branchen-Configs |
| `akquise/settings.json` | Standort, Crawl-Limits |
