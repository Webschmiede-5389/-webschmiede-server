# Webschmiede Platform – Go-Live Checkliste

**Stand:** 22. Juli 2026 · **Live:** https://digitalehandwerkskunst.de/

## Erledigt (automatisch)

- [x] Agency-Build deployed → `/var/www/digitalehandwerkskunst`
- [x] `/support` – Support-Ticket + SLA
- [x] `/#kalkulator` – Preis-Kalkulator (B2B)
- [x] `/impressum` – § 5 DDG
- [x] `/datenschutz` – DSGVO inkl. n8n, Meta, WhatsApp, DocuSeal, Hetzner
- [x] n8n-Workflows importiert (4 Stück)
- [x] n8n Log-Pruning: `EXECUTIONS_DATA_MAX_AGE=168` (7 Tage)

## Manuell in n8n (einmalig)

Öffnen: https://digitalehandwerkskunst.de/n8n/

Diese Workflows **aktivieren** (Toggle oben rechts):

| Workflow | Webhook |
|----------|---------|
| Webschmiede – Support Ticket | `/n8n/webhook/support-ticket` |
| Webschmiede – Contract Request (Kalkulator) | `/n8n/webhook/contract-request` |
| Webschmiede – Contract Completed → CRM | `/n8n/webhook/contract-completed` |

**Global Error Handler:** Settings → Error Workflow → „Webschmiede – Global Error Handler“ wählen.

### Env auf auto-Server (`/opt/n8n/.env`)

```
TELEGRAM_BOT_TOKEN=...
TELEGRAM_NILS_CHAT_ID=...      # Ops/Support/Fehler → Nils
TELEGRAM_STEFAN_CHAT_ID=...    # Verträge/Anfragen → Stefan
TELEGRAM_OWNER_CHAT_ID=...     # Fallback (gleicher Nils-Bot-Chat)
CRON_SECRET=...
AGENCY_ADMIN_PASSWORD=...
```

**Kein SMTP nötig** – alles läuft über Telegram + Agency Brain (`/api/agency/brain`).

### Routing

| Event | Agent |
|-------|--------|
| Support-Ticket | Nils (+ Stefan bei kritisch) |
| Kalkulator/Vertrag | Stefan |
| Vertrag signiert | Stefan + Nils |
| n8n-Fehler | Nils |

## Test nach Aktivierung

```bash
curl -X POST https://digitalehandwerkskunst.de/n8n/webhook/support-ticket \
  -H "Content-Type: application/json" \
  -d '{"subject":"Test","priority":"normal","message":"Hi","name":"Test","email":"info@digitalehandwerkskunst.de"}'
```

Erwartung: HTTP 200 + `{"ok":true,"ticket_id":"TKT-..."}`

## Deploy erneut ausführen

```bash
cd agency-web && npm run build
cd .. && python scripts/deploy_agency.py
```

## n8n erneut importieren

```bash
python scripts/setup_webschmiede_platform_n8n.py
python scripts/setup_webschmiede_platform_n8n.py --activate-only
```
