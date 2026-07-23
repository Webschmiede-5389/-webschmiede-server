# Topic: auto-01 Migration (Auto-01neu)

Stand: 2026-07-17

## Neu

| Rolle | Hostname | IP | Inhalt |
|-------|----------|-----|--------|
| auto (neu) | Auto-01neu | `88.198.170.156` | n8n, Cron, Akquise, Watchdog |

## Alt (abschalten nach OK)

| auto-01 alt | `204.168.174.152` | **gestoppt** 17.07. (n8n off, cron leer) · kann gekündigt werden |

## Migriert

- `/opt/n8n` (Daten + .env)
- `/root/app/scripts`, `akquise`, `kunden`, secrets
- Crontab (Akquise, Watchdog, Backup, Hetzner Buyer)
- web-01 nginx: n8n proxy → `88.198.170.156:5678`

## Skripte

- `scripts/hetzner_rebuild_by_ip.py` — Ubuntu 24.04 Rebuild
- `scripts/hetzner_fix_root_password.py` — Root-PW + Expiry
- `scripts/migrate_auto01_to_new.py` — Vollmigration

## deploy.secrets.local

`AUTO_HOST=88.198.170.156` · Passwort nur lokal (nicht committen)
