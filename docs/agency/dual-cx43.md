# Dual CX43 (Nuernberg) – Lastenverteilung & Ops

Stand: 2026-07-19

## Live-Topology (ehrlich)

| Rolle | Host | Aufgabe |
|-------|------|---------|
| **Gesicht & Daten** | web-01neu `167.233.150.230` | snack-api, nginx, Dashboards, SQLite, Uploads |
| **Gehirn & Kette** | auto-01neu `88.198.170.156` | n8n, Cron, Voice-Demo |

Beide: ~16 GB RAM, Nuernberg, Hetzner (ISO 27001 beim Anbieter).  
**Kein Helsinki.** Noch **kein** dedizierter Postgres-db-01.

## Router (WF1)

Oeffentlich: `https://digitalehandwerkskunst.de/api/agency/router`  
nginx auf web → snack-api. `/n8n/` wird zu auto geproxyt.  
Security: `docs/agency/router-security.md`

## Nils Dual-Watch

```bash
python scripts/dual_cx43_watch.py
python scripts/dual_cx43_watch.py --mail-on-alert
python scripts/setup_dual_cx43_cron.py   # Cron auf web+auto
```

API (Agency-Auth): `GET /api/nils/dual-status`  
Router-Meta: `GET /api/agency/router/security` (Feld `dual`)

## Cross-Backup

Script: `scripts/backup_cross_peers.sh` (AES mit `BACKUP_ENCRYPT_PASSPHRASE`)  
Peer-Push: `BACKUP_PEER_*` (setzt `scripts/sync_dual_secrets.py`).  
SSH zwischen Peers: Firewall `webschmiede-dual` muss Port 22 von web↔auto erlauben  
(`python scripts/open_dual_ssh_firewall.py`). Heim-IP bleibt erlaubt.

## Pitch an Grosskunden (sicher)

„Automation und Kunden-Portal laufen auf getrennten Hetzner-Servern in Nuernberg (DE).  
Anbieter ISO 27001. Keine US-All-in-One-Pflicht.“

Nicht behaupten: physische DB-Spiegelung Enterprise-Klasse / Postgres-HA – das kommt erst bei Trigger (`docs/agency/postgres-migration.md`).
