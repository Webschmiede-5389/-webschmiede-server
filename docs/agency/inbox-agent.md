# Agency E-Mail-Agent (Phase 1)

Automatische FAQ-Antworten, Queue im Dashboard, Abend-Digest, CSV-Export.

## URLs

| Was | URL |
|-----|-----|
| Dashboard | https://digitalehandwerkskunst.de/agency → Tab **Posteingang** |
| FAQ bearbeiten | `app/jarvis/inbox_faq.json` |
| API (n8n) | `POST /api/inbox/process` (Header `X-Cron-Secret`) |
| Abend-Digest | `POST /api/cron/inbox-digest` (18:00 via n8n) |

## Einrichtung (einmalig)

### 1. IONOS IMAP in n8n

**Stand 16.07.2026:** Credentials `Agency IMAP (info@)` und `Agency SMTP (info@)` sind auf auto-01 importiert, Workflows aktiv.

Falls neu aufsetzen – n8n → Credentials → **IMAP**:

- Host: `imap.ionos.de`
- Port: `993` (SSL)
- User: `info@digitalehandwerkskunst.de`
- Passwort: Postfach-Passwort (wie SMTP)

### 2. Workflows importieren

```bash
python scripts/import_n8n_workflows.py
```

Oder manuell in n8n UI:

- `infra/n8n/workflow-inbox-agent.json`
- `infra/n8n/workflow-inbox-digest.json`

### 3. n8n Variables

- `CRON_SECRET` = Wert aus `/root/app/backend/.env`

### 4. Agency Owner E-Mail

Im Setup-Portal (`/agency-setup`):

- **Deine Agency-E-Mail** → Empfänger für Abend-Digest + Dringend-Alerts

### 5. Workflows aktivieren

Beide Workflows in n8n auf **Active**.

## Status-Stufen

| Status | Bedeutung |
|--------|-----------|
| `auto` | FAQ erkannt, Antwort gesendet |
| `pending` | Manuell bearbeiten (Abend-Liste) |
| `urgent` | Dringend — Sofort-Mail an dich |
| `ignored` | Spam/Werbung |
| `manual_done` | Im Dashboard als erledigt markiert |

## Excel

Dashboard → **CSV / Excel** → Datei in Excel/LibreOffice öffnen (Semicolon-getrennt).

## FAQ erweitern

`app/jarvis/inbox_faq.json` → `keywords` + `reply_text` / `reply_html` → `python deploy.py`
