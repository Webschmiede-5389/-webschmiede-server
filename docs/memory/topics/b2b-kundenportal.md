# B2B Kundenportal

Stand: 2026-07-19

## Beschluss

Kein Budibase als Pflicht. Eigenes Flask-Portal als Gesicht fuer n8n.

## Live

- UI: `/b2b-portal.html`
- API: `/api/b2b/jobs/*`
- Optional n8n: `infra/n8n/workflow-b2b-wholesale.json` + Env `B2B_WHOLESALE_WEBHOOK`
- Budibase-Compose nur Skizze: `infra/docker/budibase.compose.yml` (nicht installiert)

## Naechster Schritt

Keepa nur nach Kosten-OK. Optional Tenant-Login pro Kunde statt Agency-Passwort.
