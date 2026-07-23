# Topic: Freigabe-Check (Shipcheck)

Stand: 2026-07-19

## Beschluss

Keine Live-Links / Dashboards an Christian ohne vorherigen HTTP-Smoke (`agency_shipcheck`).

## Technik

- `app/backend/agency_shipcheck.py`
- CLI `scripts/shipcheck_cli.py`
- API `POST /api/agency/shipcheck`
- Router-Agent `shipcheck` (WF15)
- Hirn auto-gated bei `https://` in der Nachricht
- Cursor Rule `.cursor/rules/shipcheck.mdc`

## Nächster Schritt

Live: Deploy ok, API `ship=true` für health. Cursor-Rule aktiv.
