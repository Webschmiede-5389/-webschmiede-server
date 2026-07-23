# Akquise-Krieger: Vollautomatisierung lokal (Mechernich / Euskirchen)

Stand: Juli 2026.

## Läuft

| Baustein | Status |
|----------|--------|
| OSM + Dual-Center (Mechernich + Euskirchen) | aktiv |
| Website-Crawl, Places, Ads, Register-Hook | aktiv |
| Kauf-Signale A/B (Lieferando-Lücke, Ads, Jobs, Google zu) | aktiv |
| Add-on-Katalog + ROI + Call-Skript | aktiv |
| Reverse-Nachfrage + Lokal-News + Markt (Jobs/Insolvenz) | aktiv |
| Freigabe-UI `/akquise-freigabe.html` | aktiv |
| Reminder-API + n8n-Template | aktiv |
| Kleinanzeigen leichter Scan | aktiv (Anbieter-Anzeigen gefiltert) |
| Quoka / nexxt / Dark | gastro, handwerk, friseur, dach, elektro, **trockenbau, fliesenleger, gartenbau, hochbau, tiefbau** |
| Nightly Rotation | Mo gastro, Di fliesen, Mi dach, Do trockenbau, Fr elektro, Sa gartenbau, So hochbau/tiefbau |
| Dark Plurality Katalog + Watch | aktiv · `dark_sources.json` / `forums.md` |
| Auftragsbank + Forum-Watch (nebenan manuell) | aktiv · siehe `forums.md` |
| North Data | nur mit Key |
| Retell Telefon | separat, siehe Voice-Doku |

## Freigabe (UWG)

1. Nightly erzeugt Reports
2. Du öffnest `/akquise-freigabe.html` → Anrufen / Später / Skip
3. Bei „Später“: Reminder in 3 Tagen (Cron/n8n → Mail)

## Befehle

```bash
python scripts/akquise_run.py --vertical gastro
python scripts/akquise_demand_scan.py
python scripts/akquise_local_news.py
python scripts/akquise_market_signals.py
```

## n8n

Import: `infra/n8n/workflow-akquise-reminders.json`  
Endpoint: `POST /api/cron/akquise-reminders` mit `X-Cron-Secret`

## Retell (du persönlich)

Produktion Telefon = Retell, nicht CX43. Siehe `docs/agency/voice-agents.md`.
