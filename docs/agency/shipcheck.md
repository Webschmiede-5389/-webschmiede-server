# Freigabe-Check (Shipcheck / WF15)

Bevor Links oder Dashboards an Christian (oder Kunden) gehen: HTTP-Smoke. Rot = nicht schicken.

## Warum

Toter Link oder 404 nach Deploy kostet Vertrauen. Der Check ist Pflicht, kein „sollte gehen“.

## Nutzung

```bash
python scripts/shipcheck_cli.py "https://digitalehandwerkskunst.de/api/health"
python scripts/shipcheck_cli.py --dashboard agency-setup
python scripts/shipcheck_cli.py --dashboard b2b
```

API (Agency-Auth):

```http
POST /api/agency/shipcheck
{"text": "schau https://…"}
{"urls": ["https://…"]}
{"dashboard": "health"}
```

Antwort: `"ship": true` → freigeben. `"ship": false` → erst reparieren.

## Cursor

Regel `.cursor/rules/shipcheck.mdc` (alwaysApply): Agent nennt keine Live-Links ohne Check.

Hirn (`agency_brain`): enthält die Nachricht `https://…`, läuft Shipcheck automatisch mit.

## Kurznamen

| Key | URL |
|-----|-----|
| agency-setup | `/agency-setup` |
| b2b | `/b2b-portal.html` |
| health | `/api/health` |
| yassine | yassine Subdomain |
| whatsapp-webhook | WhatsApp Webhook |

## Grenze

Prüft Erreichbarkeit/Status, nicht die volle UI-Logik. Auth-APIs mit 401 können OK sein (erreichbar).
