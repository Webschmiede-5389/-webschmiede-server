# 13 Kern-Workflows (Webschmiede)

Stand: 2026-07-19  
Keine 50 Personalakten. **15 klare Jobs** (13 Kern + Radar + Freigabe-Check). Router = Gehirn.

## Hirn scharf (2026-07-19)

- **API:** `POST /api/agency/brain` `{ "message": "…" }` → Router + Dispatch  
- **CLI:** `python scripts/agency_brain_cli.py "…"`  
- **n8n:** `workflow-agency-brain.json` (+ Import `scripts/import_agency_brain_n8n.py`)  
- **Cursor:** Rule `.cursor/rules/agency-brain.mdc` (Chat wird nicht magisch mitgelesen)

## Ehrlicher Status

| # | Name | Status | Wo |
|---|------|--------|-----|
| 1 | Router | **live + Dispatch** | `agency_brain.py` + `agency_router.py` |
| 2 | Stefan | **live** | plan + growth + filter · Commander-Pack `/api/agency/commander/*` |
| 3 | Markt-Scout | **live** | `/api/agency/scout/campaign` + akquise Reports |
| 4 | Outreach | **live** | Entwürfe in Scout-Campaign, Send nur mit Freigabe |
| 5 | CRM Follow-Up | **live** | `workflow-followups.json`, akquise-reminders |
| 6 | Texter | **live** | Skill `texter` |
| 7 | Design | **live** | Skill `design` |
| 8 | Lektor | **live** | Teil von Skill `texter` |
| 9 | Nils | **live** | Skill `nils`, healthcheck, watchdog |
| 10 | Anwalt | **live** | Skill `anwalt` (Vorprüfung, nicht wasserdicht) |
| 11 | Finanz | **partial** | Buchhaltung-n8n, DocuSeal, Meta-Rechnungen |
| 12 | Account-Manager | **live** | inbox-agent + digest |
| 13 | Service-Wächter | **live** | nightly_watchdog, resource_watchdog |
| 14 | Radar / Trend-Scout | **live** | `agency_radar.py`, Wochenreport, Install-Queue |
| 15 | Freigabe-Check | **live** | `agency_shipcheck.py`, Links nur bei `ship=true` |

`partial` = Kern da, nicht jeder Guru-Schritt 1:1 automatisiert.

## Nutzen

- Cursor: „Router: …“ oder gemischte Aufträge → Playbook  
- CLI: `python scripts/agency_router_cli.py --playbook "…"`  
- Register: `GET /api/agency/workflows`  
- n8n-Stubs: `infra/n8n/agency-system/` (generieren: `python scripts/gen_agency_n8n_stubs.py`)

## n8n Import

1. Stubs erzeugen: `python scripts/gen_agency_n8n_stubs.py`
2. In n8n: Ordner `infra/n8n/agency-system/*.json` importieren (alle **inactive**)
3. Env: `CRON_SECRET`, ggf. `AGENCY_ADMIN_PASSWORD`
4. Router produktiv: zusätzlich `workflow-agency-router.json` aktivieren
5. Cron-Workflows (05, 09, 13) nur aktivieren wenn Endpunkte + Secrets sitzen

## Was wir bewusst nicht bauen

- Notion/Airtable als Pflicht (wir haben eigenes CRM/SQLite)
- Auto-Spam Outreach
- „Top-5-Kanzlei“-Garantie ohne echten Anwalt
- 50 Fake-Mitarbeiter mit Personalakte

## Nächster Ausbau (Reihenfolge)

1. Frische Akquise-Reports pro Vertical (Places-Key, Kosten-OK)
2. Christian: 5 Entwürfe/Tag freigeben
3. Optional LLM in n8n nur mit API-Key + Budget-OK
