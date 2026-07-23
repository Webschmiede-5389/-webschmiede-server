# Topic: 13-Workflow-System

## Stand 2026-07-19

Umsetzung der „13 Kern-Workflows“-Architektur (kein 50er-Guru-Pack) + Radar + Shipcheck.

- Map: `docs/agency/13-workflows.md`
- Router: Agenten inkl. `radar` (14) + `shipcheck` (15)
- Skills: texter, design (+ anwalt, nils, stefan, router)
- n8n: `infra/n8n/agency-system/` via `scripts/gen_agency_n8n_stubs.py`
- API: `/api/agency/workflows`, `/api/agency/shipcheck`

## Wahrheit

Vieles war schon da (Watchdog, Inbox, Follow-ups, Akquise). Neu: einheitliche Map + Skills + Stubs + Freigabe-Check vor Links.
