# Topic: AI-Router

## Stand 2026-07-19

- `app/backend/agency_router.py` + `POST /api/agency/router`
- n8n: `infra/n8n/workflow-agency-router.json`
- Schema: `infra/n8n/router-schema.json`
- Cursor: Skill `router`, Rule `router.mdc`
- CLI: `scripts/agency_router_cli.py`
- Doku: `docs/agency/ai-router.md`

## Nächster Schritt

1. `python deploy.py` (API live)
2. n8n Workflow importieren, `CRON_SECRET` setzen, aktivieren
3. Optional: Texter-Skill (B), Sub-Workflows statt Stubs
