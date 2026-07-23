# Trend-Scout / Radar (Mitarbeiter WF14)

Stand: 2026-07-19

> Wöchentlicher Scan: LLMs, Open Source, Design, Video, Social, Automation.  
> Output: Report für Christian. **Kein Auto-Install ohne Freigabe.**

## Rolle

**Radar** beobachtet den Markt und die eigenen Workflows.  
**Nils** installiert erst nach deinem OK.  
**Stefan** priorisiert, was davon Umsatz bringt.

## Scope

| Bereich | Beispiele |
|---------|-----------|
| LLM / API | OSS-Modelle, günstige APIs, Ollama |
| Design | Tools die zu Dunkel+Gold passen |
| Video / Reels | lokale oder API-Clips DE |
| Social | Scheduling, Caption (eigene Kommentare only) |
| Automation | n8n Nodes, Webhooks, ohne GHL |
| Voice | STT/TTS (Demo self-host vs Retell) |
| Wissen | awesome-selfhosted, HF, Foren-Links |

## Befehle

```bash
python scripts/trend_scout_report.py          # Wochenreport
python scripts/radar_cli.py status
python scripts/radar_cli.py queue
python scripts/radar_cli.py add --name "Tool X" --reason "warum"
python scripts/radar_cli.py approve --id rad001
```

API (Agency-Auth):

- `GET /api/agency/radar/status`
- `POST /api/agency/radar/scan`
- `GET/POST /api/agency/radar/queue`
- `POST /api/agency/radar/queue/<id>/decide` `{ "approve": true }`

Report: `docs/agency/reports/YYYY-MM-DD-radar.md`  
Queue: `agency/radar_queue.json`

## Automatisch (live)

- **n8n:** `Agency 14 – Radar Wochen-Scan` · Freitag 07:00 (`0 7 * * 5`)
- **web-Cron Backup:** Freitag 07:05 `/root/app/scripts/radar_weekly.sh` → Log `/var/log/agency-radar.log`
- Setup: `python scripts/setup_radar_weekly.py`

## Automatisierung

1. Freitags Report (CLI oder n8n)
2. Optional Mail an `AGENCY_OWNER_EMAIL`
3. Christian: „install X“ / Queue approve → Nils + Smoke-Test
