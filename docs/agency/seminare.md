# Webschmiede — Seminare & Termine (Hybrid)

## Übersicht

| Art | URL | Technik |
|-----|-----|---------|
| **1:1 Erstgespräch** | `/cal/` | Cal.com (self-hosted oder Cloud) |
| **Seminare (Kapazität)** | `/seminare` | Eigenes Flask-Modul + SQLite |
| **Agency Admin** | `/agency` | Passwort `AGENCY_ADMIN_PASSWORD` |

## Öffentliche Seite

- `https://digitalehandwerkskunst.de/seminare` — Liste + Anmeldung
- Demo-Seminar wird beim ersten Start automatisch angelegt

## API

```
GET  /api/seminars                    # Öffentliche Liste + calcom_url
POST /api/seminars/:id/register       # Anmeldung (Rate-Limit)
GET  /api/agency/seminars             # Admin (Header: X-Agency-Password)
POST /api/agency/seminars             # Neues Seminar
PUT  /api/agency/seminars/:id         # Bearbeiten
GET  /api/agency/seminars/:id/registrations
DELETE /api/agency/registrations/:id  # Storno
```

## Server-Setup

```bash
# Code deployen
python deploy.py

# Nginx-Routen (einmalig)
python nginx_add_routes.py

# Cal.com (optional, self-hosted)
python setup_calcom.py

# n8n-Workflow importieren
# infra/n8n/workflow-seminar-anmeldung.json
# Webhook-URL in .env:
# N8N_SEMINAR_WEBHOOK=http://167.233.211.170/n8n/webhook/seminar-registration
```

## Umgebungsvariablen (Server `.env`)

```
AGENCY_ADMIN_PASSWORD=...
AGENCY_OWNER_EMAIL=you@webschmiede.de
CALCOM_URL=http://167.233.211.170/cal
N8N_SEMINAR_WEBHOOK=http://167.233.211.170/n8n/webhook/seminar-registration
```

Agency-SMTP für Bestätigungs-Mails: `deploy.secrets.local` → `AGENCY_SMTP_*`

## Google Calendar

Cal.com mit Google verbinden (Settings → Calendars). Seminare bleiben im eigenen System — kein Google-Limit bei vielen Teilnehmern.
