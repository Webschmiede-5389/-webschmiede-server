# Topic: web-01 Migration (Helsinki → Nürnberg)

Stand: 2026-07-17

## Zielbild (2 Server DE)

| Server | IP | Rolle |
|--------|-----|--------|
| **web-01neu** | `167.233.150.230` | Nginx, API, Portale, Agency, Cal.com |
| **auto-01neu** | `88.198.170.156` | n8n, Cron, Akquise, Voice-Demo :8090 |

## Migriert

- `/root/app`, Nginx, Let's Encrypt, `/var/www`, snack-api
- Voice-Demo von Voice-01neu → **auto-01neu** (docker)
- `deploy.secrets.local`: `WEB_HOST=167.233.150.230`

## Christian: DNS

**Cloudflare-Zone steht** (pending). Bei IONOS Nameserver setzen:

- `phil.ns.cloudflare.com`
- `vera.ns.cloudflare.com`

Details: `docs/agency/cloudflare-agency-dns.md`

Danach Helsinki CX33 kündigen.

## Status 2026-07-17

Helsinki **gelöscht** (Hetzner API: poweroff + delete `Web-01` id 151620037).  
Öffentliches DNS und Traffic nur noch web-01neu.


## Smoke (auf neuem Server per Host-Header)

- `/api/health` → 200
- `/voice-demo/api/health` → 200 (Proxy → auto:8090)

## Kündigen nach DNS-Umstellung + Test

- CX33 Helsinki `204.168.170.97` (alter web-01)
- Voice-only CX43 falls nicht mehr genutzt (war `167.233.150.230`, jetzt web)

## Skripte

- `scripts/migrate_web_to_nbg.py`
- `scripts/fix_web01neu_nginx.py`

## Offen

- Cal.com: frisches DB-Volume (Alt-Volume von Helsinki nicht per SSH erreichbar — ggf. neu einrichten)
- Cal-Buchungen von alt: manuell falls nötig
