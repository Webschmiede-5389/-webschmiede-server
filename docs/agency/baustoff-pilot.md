# Baustoffhandel Standort-Pilot

Stand: 2026-07-19

## Ziel

30-Tage-Pilot an **einem Standort** (Baustoff-/Fachhandel):  
keine Standardsoftware, sondern drei digitale Mitarbeiter-Flows.

## Use Cases (ehrlich)

| # | Use Case | Status |
|---|----------|--------|
| 1 | WhatsApp-Bestellentwurf + Freigabe-Queue | Demo live (Meta-Inbound fehlt noch) |
| 2 | Preislisten-Vergleich (CSV A vs B, Ausreisser) | Live |
| 3 | Reklamations-Vorsortierung | Live (ohne ERP-Lookup) |

Hosting: Hetzner Nuernberg. Kein Helsinki. Kein Auto-Send an Kunden.

## API (Agency/B2B-Auth)

- `GET /api/b2b/baustoff/pilot`
- `POST /api/b2b/baustoff/parse-order` `{text, kunde_id, save}`
- `GET /api/b2b/baustoff/orders` · `POST .../orders/<id>/approve`
- `POST /api/b2b/baustoff/compare` multipart `file_a`, `file_b`
- `POST /api/b2b/baustoff/complaint` `{subject, text}`

Portal: `/b2b-portal.html` (Tabs Preisvergleich, WA-Bestellung, Reklamation)

## Demo lokal

```bash
python scripts/baustoff_pilot_demo.py
```

## Scout / Akquise

- Vertical: `akquise/verticals/baustoff.json`
- Outreach: `vertical=baustoff` → Pilot-Text in `agency_scout.py`
- n8n Stub (inaktiv): `infra/n8n/workflow-b2b-baustoff.json`

## Pitch (30 Tage)

Lassen Sie uns an einem Standort WhatsApp-Bestellungen von wenigen Stamm-Handwerkern  
und/oder den Preislisten-Abgleich 30 Tage laufen. Mitarbeiter geben nur frei.  
Wenn Zeit gespart wird: Monatsmodell. Sonst abschalten.

## Noch nicht

- Meta WhatsApp Business Token (Inbound)
- Echter ERP-Bestand / Lieferschein-API
- Automatisches Lesen eines Einkaufs-Postfachs (n8n spaeter)
