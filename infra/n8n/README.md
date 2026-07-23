# n8n – Webschmiede Automation Hub

## URL

https://digitalehandwerkskunst.de/n8n/

Login: siehe `n8n-credentials.local.txt` (lokal, nicht in Git).

## Workflows importieren

Neuer Kunde: `python jarvis.py neu` legt automatisch **eigene n8n-Workflows** an (`SHY002 – …`).

Manuell nachziehen: `python jarvis.py n8n SHY002`

Pro Kunde in n8n (getrennt von Agency-Workflows):

| Workflow | Gastro | Handwerk |
|----------|--------|----------|
| Bestell-/Anfrage-Alert | `{ID} – Neue Bestellung Alert` | `{ID} – Neue Anfrage Alert` |
| Monats-Buchhaltung | `{ID} – Monats-Buchhaltung` | `{ID} – Monats-Buchhaltung` |

Webhook aus `kunden/*.json` → `n8n.order_webhook` bzw. `n8n.anfrage_webhook`.

Alternativ manuell: n8n UI → **Import from File** (REST-API braucht `X-N8N-API-KEY`).

Dateien aus `infra/n8n/`:
   - `workflow-followups.json` — Review/Win-back (10:00)
   - `workflow-healthcheck.json` — API alle 15 Min
   - `workflow-backup.json` — DB-Backup (03:00)
   - `workflow-new-order-alert.json` — **Neue Bestellung → SMS/E-Mail an Inhaber**
   - `workflow-beleg-archiv.json` — E-Mail-Belege archivieren (Agency)
   - `workflow-meta-rechnungen.json` — **Meta-Werberechnungen → Buchhaltung**
   - `workflow-buchhaltung-monat.json` — **1. des Monats: Umsatz-CSV an Buchhaltung**
   - `workflow-monatsreport.json` — Montags SHY001 Report an dich
   - `workflow-inbox-agent.json` — **Agency Posteingang → FAQ + Queue**
   - `workflow-inbox-digest.json` — **Abend-Briefing 18:00**
   - `workflow-whatsapp-outbound.json` — **Skizze: WA-Template über Agency-API** (erst nach Meta-Token)
   - `workflow-agency-router.json` — **AI-Router / Dispatcher** (Intent → 13er-System)
   - `agency-system/*.json` — **13 Kern-Workflow-Stubs** (`python scripts/gen_agency_n8n_stubs.py`)

Details: `docs/agency/13-workflows.md` · `docs/agency/ai-router.md`  
Details E-Mail-Agent: `docs/agency/inbox-agent.md`  
Buchhaltung / Meta: `docs/agency/buchhaltung-setup.md`

## E-Mail-Agent (Agency Posteingang)

1. IMAP-Credential in n8n: `imap.ionos.de:993` + `info@digitalehandwerkskunst.de`
2. `workflow-inbox-agent.json` + `workflow-inbox-digest.json` importieren → aktivieren
3. `CRON_SECRET` in n8n Variables
4. `AGENCY_OWNER_EMAIL` im Setup-Portal (`/agency-setup`)
5. Dashboard: https://digitalehandwerkskunst.de/agency → Tab **Posteingang**


1. `workflow-new-order-alert.json` importieren → Workflow **aktivieren**
2. n8n → Variables:
   - `SEVEN_API_KEY` = seven.io Key
   - `OWNER_PHONE` = Hassan Handynummer (+49…)
   - `SMS_SENDER` = SnackHouse
   - `ALERT_TO_EMAIL` = yassinehassan910@gmail.com (Backup)
3. Webhook-URL kopieren (z. B. `http://127.0.0.1:5678/webhook/new-order-shy001`)
4. Auf Server in `/root/app/backend/.env`:
   ```
   N8N_ORDER_WEBHOOK=http://127.0.0.1:5678/webhook/new-order-shy001
   ```
5. `systemctl restart snack-api`

Oder: `python scripts/go_live.py SHY001 configure --n8n-webhook URL`

**Hinweis:** Flask sendet bei jeder Bestellung parallel SMS direkt (wenn `SMS_ENABLED`). n8n ist Backup + E-Mail.

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
