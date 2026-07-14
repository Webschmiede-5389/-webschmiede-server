# n8n – Webschmiede Automation Hub

## URL

http://167.233.211.170/n8n/

Login: siehe `n8n-credentials.local.txt` (lokal, nicht in Git).

## Workflows importieren

1. n8n öffnen → **Workflows** → **Import from File**
2. Dateien aus `infra/n8n/`:
   - `workflow-followups.json` — Review/Win-back (10:00)
   - `workflow-healthcheck.json` — API alle 15 Min
   - `workflow-backup.json` — DB-Backup (03:00)

## CRON_SECRET in n8n

Settings → Variables → `CRON_SECRET` = Wert aus `/root/app/backend/.env`

(Oder in HTTP-Node Header manuell eintragen.)

## Bereits aktiv ohne n8n

- Shell-Cron: `/root/app/scripts/run_followups.sh` (10:00)
- Shell-Cron: `/root/app/scripts/backup_db.sh` (03:00)

n8n kann diese Jobs **ersetzen oder erweitern** (E-Mail bei Fehler, Slack, etc.).

## Neu installieren

```bash
python setup_n8n.py
```
