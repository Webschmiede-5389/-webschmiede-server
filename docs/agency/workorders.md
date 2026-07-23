# Workorders (Telegram → Umsetzung)

Stand: 2026-07-19

## Direkt umsetzbar (Live)

Telegram / Dashboard:

- `SHY001 Telefon auf +4917…`
- `SHY001 Tisch-Promo auf Erste Bestellung 10%`
- `SHY001 Status auf live`
- `SHY001 Notiz: Termin Dienstag`

→ schreibt `kunden/*.json` sofort.

## Cursor-Handoff / Cloud Agent

Freie Website/Design/Code-Aufträge:

- `baue Website …` / `programmiere …` / `cursor: …`

→ mit `CURSOR_API_KEY`: Cursor Cloud Agent (wie IDE) + Workorder  
→ ohne Key: `docs/memory/workorders/{id}.md` Handoff

Doku: `docs/agency/nils-cursor-bridge.md`

## UI / API

- `/workorders.html`
- `GET/POST /api/agency/workorders`
- n8n: `workflow-workorders.json`

## Grenze

Kein Blind-HTML-Edit beliebiger Dateien per Chat. Kunden-Portal-Texte über JSON. Agency-React/große Umbauten = Handoff.
