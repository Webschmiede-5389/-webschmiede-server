# Enterprise DSGVO & Vendor Assessment (Webschmiede)

Stand: 2026-07-19

## Haltung

Eigenes Cursor/Flask-Dashboard statt Budibase.  
Gegenüber Großkunden: ehrliche Fakten, keine Helsinki-Mythen, keine „wasserdicht“-Claims ohne Anwalt.

## Was schon da ist

| Baustein | Status |
|----------|--------|
| Hosting Hetzner DE (Nürnberg) | live |
| HTTPS/TLS | live |
| AVV/AGB/Auftrag DocuSeal | live (Vorlage, KI-Vorprüfung) |
| Anwalt Skill + Checkliste | live |
| Enterprise-Pack API | `/api/agency/anwalt/enterprise` |
| B2B Zero-Retention 24h | live (Portal-Checkbox, Nightly Purge) |
| n8n Credential-Encryption | `N8N_ENCRYPTION_KEY` |
| n8n Log-Härtung | `scripts/harden_n8n_logs.py` (Host **auto**, nicht web) |
| Ops-Log Purge 90 Tage | nightly_watchdog |

## Offen (Christian)

1. Hetzner AVV in Console laden → `docs/agency/hetzner-avv.md`
2. Vor erstem Enterprise: echter Anwalt → `docs/agency/vertraege/ANWALT-BRIEFING.md`
3. Optional später: App-Layer DB-Encryption / LUKS (nur nach OK)

## Vendor Assessment Kurzantworten

- **Wo liegen Daten?** Hetzner Cloud, Nürnberg, EU  
- **AVV Hosting?** Hetzner Console (eure Unterlage)  
- **AVV Kunde?** DocuSeal Kundenpaket  
- **In transit?** HTTPS/TLS  
- **At rest (App)?** noch keine App-DB-Verschlüsselung – so sagen, nicht schöner reden  
- **Retention Uploads?** Zero-Retention Option 24h im B2B-Portal  
- **Subprozessoren?** nur soweit gebucht, Liste in AVV  

## Tools

```bash
python scripts/anwalt_enterprise_cli.py --firma "Kunde GmbH" --budget "5000"
python scripts/harden_n8n_logs.py
```

API (Agency-Auth): `POST /api/agency/anwalt/enterprise`  
JSON z. B. `{"firma":"…","leistungen":"…","zero_retention":true,"budget":"5000"}`

Read-only: `GET /api/agency/anwalt/hosting-truth`

## Disclaimer

Kein Ersatz für Rechtsberatung. KI bereitet vor, Anwalt gibt frei.
