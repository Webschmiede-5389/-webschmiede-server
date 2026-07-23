# Agency-Website (digitalehandwerkskunst.de)

Quellcode der **Webschmiede – Digitale Handwerkskunst** Marketing-Site.

**Live:** https://digitalehandwerkskunst.de/

## Features (Stand Juli 2026)

| Modul | Route / Pfad |
|-------|----------------|
| Marketing-Startseite | `/` |
| Support-Ticket + SLA | `/support` |
| Impressum (§ 5 DDG) | `/impressum` |
| Datenschutz (DSGVO) | `/datenschutz` |
| Markenhinweise | `/markenhinweise` |
| Leistungen (3 Stufen) | `/#loesungen` |
| Branchen-Pakete | entfernt → Redirect `/angebote.html` → `/#loesungen` |

## Lokal entwickeln

```bash
cd agency-web
cp .env.example .env.local
npm install
npm run dev
```

Build:

```bash
npm run build
# → dist/
```

## Deploy (Hetzner)

```bash
cd agency-web && npm run build
cd .. && python scripts/deploy_agency.py
python setup_agency_nginx.py
# Nach DNS: python setup_agency_nginx.py --ssl
```

**Webroot:** `/var/www/digitalehandwerkskunst`

## n8n-Workflows (Server)

Importieren aus `../infra/n8n/`:

| Datei | Webhook-Pfad |
|-------|----------------|
| `support-ticket.json` | `/n8n/webhook/support-ticket` |
| `contract-request.json` | `/n8n/webhook/contract-request` |
| `contract-completed.json` | `/n8n/webhook/contract-completed` |
| `global-error-handler.json` | Error Workflow (Settings) |

**DSGVO Log-Pruning:** `infra/n8n/docker-compose.n8n.override.yml` oder `n8n.env.example`

```bash
# Auf Server (bestehende Secrets nicht überschreiben):
EXECUTIONS_DATA_PRUNE=true
EXECUTIONS_DATA_MAX_AGE=168
```

Oder: `python scripts/harden_n8n_logs.py` (setzt aktuell 24h – auf 168 anpassen wenn gewünscht)

## DocuSeal

```bash
# Kombi-Vertrag (Hauptvertrag + AVV) an Kunden senden
npm run contract:send -- --email kunde@firma.de --name "Max Mustermann" --company "Firma GmbH"
```

Webhook-Receiver: `npm run webhook:dev` → DocuSeal zeigt auf `/api/webhooks/docuseal`

API-Modul: `lib/contracts.ts`

## Umgebungsvariablen

Siehe `.env.example`. Webhook-URLs für Production:

```
VITE_N8N_SUPPORT_WEBHOOK_URL=https://digitalehandwerkskunst.de/n8n/webhook/support-ticket
VITE_N8N_CONTRACT_WEBHOOK_URL=https://digitalehandwerkskunst.de/n8n/webhook/contract-request
```

## Projektstruktur

```
agency-web/
├── src/
│   ├── components/     Layout, SupportTicketWidget, PriceCalculator, …
│   ├── pages/          Home, Impressum, Datenschutz, Support, …
│   └── lib/config.ts   digitalehandwerkskunst.de URLs
├── lib/contracts.ts    DocuSeal API
├── server/             Webhook contract.completed
├── scripts/            CLI Vertrag senden
└── public/             angebote.html, Logos, …
```

## Wichtig

- **Snack House** Kundenportale ≠ diese Agency-Seite (`app/static/`)
- Secrets nur in `.env` auf Server, nie committen
- Nach Deploy: Support-Ticket testen, n8n-Workflows aktivieren

Details Migration: `docs/agency/replit-migration.md`
