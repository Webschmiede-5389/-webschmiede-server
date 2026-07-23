# Migration CX33 – Stand 16.07.2026

## Server

| Rolle | Hostname | IP | Status |
|-------|----------|-----|--------|
| Alt (Fallback) | ubuntu-2gb-fsn1-1 | `167.233.211.170` | snack-api/n8n gestoppt; nginx noch an |
| web-01 | web-01 | `204.168.170.97` | Nginx + snack-api + Cal.com + UFW/fail2ban |
| auto-01 | auto-01 | `204.168.174.152` | **ersetzt** durch Auto-01neu `88.198.170.156` (17.07.) |
| voice-01 | voice-01 | `62.238.43.128` | Voice installiert (gestoppt); UFW + fail2ban aktiv |

Region neu: Helsinki (`hel1`). Alt: Falkenstein.

## Cutover (erledigt)

- DNS (öffentlich, 8.8.8.8): nur **web-01**
- Live: Agency, Yassine, Muster, API, n8n-Proxy, Cal.com (HTTPS 307, healthy)
- Cron auf **auto-01**; Alter: leer
- `deploy.py` / `setup_calcom.py` → **web-01**
- Cal.com Memory-Limit **1536m** (vorher OOM/exit 129 bei 512m)

## n8n / Mail (16.07. Abend)

- Credentials **Agency IMAP** + **Agency SMTP** aus IONOS `info@…` importiert
- Workflows (Posteingang, Meta-Rechnungen, Beleg-Archiv) auf echte Credential-IDs umgestellt und aktiv
- SMTP Live-Test OK
- Kurzzeitig Crash durch leere JSON-Felder (`pinData`/`meta` = `''`) nach Credential-Rewrite, repariert; n8n wieder stabil
- Stripe im Agency-Setup noch **nicht** hinterlegt (optional)

## Voice

Bei Bedarf auf voice-01:

```bash
cd /root/app/infra/voice-demo && docker compose up -d
# UI: http://62.238.43.128:8090/  (Port ggf. in UFW öffnen)
```

## GitHub

Remote: `https://github.com/Webschmiede-5389/-webschmiede-server.git`  
Viele lokale Änderungen noch nicht committed/gepusht (erst auf Wunsch).

## Offen / bewusst

- Alter Server 2–7 Tage als Fallback behalten, dann kündigen
- Fritz.box-DNS-Cache lokal ggf. noch alte IP (Router neu starten)
- Stripe Keys im Setup-Portal nachtragen wenn Abrechnung live soll
