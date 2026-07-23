# Topic: Dual-Server Health (web + auto)

Stand: 2026-07-17

## Server

| Rolle | Host | IP | Status |
|-------|------|-----|--------|
| web-01neu | web-01neu | `167.233.150.230` | snack-api + nginx + Cal.com OK |
| auto-01neu | Auto-01neu | `88.198.170.156` | n8n + Cron + Voice-Demo OK |

## Repariert 17.07.

- Nginx: Default-Site + Tippfehler `snackhouse-yacine.de` entfernt
- Proxy `/n8n/` + `/voice-demo/` → auto `88.198.170.156`
- UFW auto: 5678/8090 von web erlaubt
- Cal.com: Prisma/DB Schema, Container **healthy** (frische DB, alte Termine verloren)
- Smoke lokal (Host-Header): api/agency/nils/n8n/voice/yassine/muster = 200, cal = 307

## Offen (Christian)

**Öffentliches DNS** zeigt noch auf alte Helsinki-IP `204.168.170.97`.  
→ Cloudflare Nameserver bei IONOS setzen (Agentur) **oder** A-Records auf `167.233.150.230`.

Ohne DNS-Umstellung laufen die neuen Server intern perfekt, öffentlich noch der alte.

## Skripte

- `scripts/repair_web_auto.py`
- `scripts/_health_both.py`
