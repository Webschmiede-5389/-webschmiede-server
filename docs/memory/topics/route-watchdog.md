# Route-Watchdog / DNS-Mismatch

Stand: 2026-07-17

## Problem

Nach Web-Migration: öffentliches DNS der Agentur-Domain zeigte noch auf alten Server. Browser → alte Setup-Seite ohne IONOS-API-Felder.

## Fix

1. IP-Zugang: `https://WEB_HOST/agency-setup`
2. A-Records bei IONOS auf WEB_HOST
3. Watchdog: `scripts/route_watchdog.py` Cron `*/15` auf auto
4. Auto-Reparatur wenn `IONOS_API_PREFIX` + `IONOS_API_SECRET` gesetzt

## Install

```bash
python scripts/setup_route_watchdog.py
```

## Status 2026-07-17

Cutover **erledigt**. IONOS A-Records auf `167.233.150.230`. Öffentliches DNS (8.8.8.8) bestätigt.
