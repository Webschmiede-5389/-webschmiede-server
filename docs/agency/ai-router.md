# Agency AI-Router

Stand: 2026-07-19

Zentrales Gehirn: Absicht erkennen → digitale Mitarbeiter delegieren.  
Kein Ersatz für Cursor-Skills; **Klassifizierung + Playbook**, Ausführung in Cursor oder später n8n-Sub-Workflows.

## Komponenten

| Teil | Pfad |
|------|------|
| Logik | `app/backend/agency_router.py` |
| API | `POST /api/agency/router` (Auth: `X-Cron-Secret` oder `X-Agency-Password`) |
| Schema | `GET /api/agency/router/schema` · `infra/n8n/router-schema.json` |
| n8n | `infra/n8n/workflow-agency-router.json` (inaktiv importieren) |
| CLI | `python scripts/agency_router_cli.py "…"` |
| Cursor | Skill `router` · Rule `router.mdc` |

## Mitarbeiter

`anwalt` · `texter` · `lektor` · `nils` · `stefan`

Regel: Text schreiben → immer **texter + lektor**.

## n8n Setup

1. Workflow importieren
2. In n8n Environment: `CRON_SECRET` = Wert vom Server (wie andere Cron-Workflows)
3. Aktivieren
4. Test:

```bash
curl -s -X POST "https://DEINE-N8N-URL/webhook/agency-router" \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"Prüfe den Vertrag und schreib ein Onboarding-Anschreiben\"}"
```

Oder direkt API:

```bash
python scripts/agency_router_cli.py --live --playbook "Prüfe den Vertrag und schreib ein Anschreiben"
```

## Optional LLM

`AGENCY_ROUTER_LLM=1` + `OPENAI_API_KEY` auf dem Server → OpenAI-Klassifizierung, sonst Regel-Engine (Standard, kein Extra-Key).

## Nächster Ausbau

Switch-Nodes → echte Sub-Workflows Anwalt/Texter (wenn API-Keys in n8n). Bis dahin: Cursor führt das `playbook` aus.
