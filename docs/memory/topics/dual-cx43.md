# Dual CX43

Stand: 2026-07-19

## Beschluss

- web (Voice01neu / hostname web-01neu) = Gesicht/Daten
- auto (Auto-01neu) = n8n/Gehirn
- Beide Nuernberg, ~16 GB RAM. Kein Helsinki, kein Fake-Postgres-HA

## Live OK

- Dual-Watch CLI + API `/api/nils/dual-status` (web=local, auto=ssh)
- Firewall `webschmiede-dual`: SSH 22 von Heim-IP + web↔auto
- Cross-Backup AES + Peer-Push beide Richtungen
- Secrets: `scripts/sync_dual_secrets.py`
- Firewall-Helper: `scripts/open_dual_ssh_firewall.py`

## Pitch (sicher)

Automation und Kunden-Portal auf getrennten Hetzner-Hosts in Nuernberg. SQLite noch auf web.
