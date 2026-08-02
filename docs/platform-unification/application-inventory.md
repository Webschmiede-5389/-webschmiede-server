# Application Inventory

**Stand:** 2026-08-02 · Read-only · JSON: [application-inventory.json](./application-inventory.json)

Methode: Repos, Static-HTML, Docker-Compose, Docs (`DIRECTION.md`, `live-kunden-audit.md`, `open-source-stack.md`, Memory), Sibling-Projekte unter `My_Company_Hub/projects/`.  
Live-HTTP-Erreichbarkeit wurde in diesem Schritt **nicht** flächig neu geprüft (kein Deploy/kein Störbetrieb). Status `documented_live` = in Agency-Docs belegt.

## Kurzfassung

| Kategorie | Anzahl (Inventur) |
|-----------|-------------------|
| Eigene interne Apps (Agency) | ~20 |
| Kundenportal SHY001 | 1 Cluster (Shop/Admin/Konto) |
| Externe Dienste | 8+ |
| Legacy / Dubletten | mehrere |
| Nicht gefunden (Uptime Kuma) | 1 als UNREACHABLE |

## Vollständige Linkliste (bekannte Production/Config-URLs)

| Name | URL | Typ |
|------|-----|-----|
| Agency Website | https://digitalehandwerkskunst.de/ | public |
| Agency Cockpit | https://digitalehandwerkskunst.de/agency | internal |
| Agency Hub | https://digitalehandwerkskunst.de/agency-hub | internal |
| Agency Setup | https://digitalehandwerkskunst.de/agency-setup | internal |
| Nils | https://digitalehandwerkskunst.de/nils | internal |
| n8n | https://digitalehandwerkskunst.de/n8n/ | external UI |
| CRM | https://crm.digitalehandwerkskunst.de | internal |
| Lead Creator / DHK Leads | https://leads.digitalehandwerkskunst.de | internal |
| Cal.com | https://cal.digitalehandwerkskunst.de | external |
| DocuSeal | https://sign.digitalehandwerkskunst.de | external |
| Umami | https://analytics.digitalehandwerkskunst.de | external |
| Radar | https://radar.digitalehandwerkskunst.de | unknown UI |
| Voice | https://voice.digitalehandwerkskunst.de | experimental |
| Snack House | https://snackhouse-yassine.de/ | customer |
| Seminare | https://digitalehandwerkskunst.de/seminare | public |
| TourMeter | https://digitalehandwerkskunst.de/transport-kalkulator.html | experimental |
| CI Vorlagen | https://digitalehandwerkskunst.de/ci/ | internal docs |

## Interne Anwendungen (Auszug)

### Priorität A

1. **Agency Cockpit** — `webschmiede-server` / `app/static/agency.html` — ACTIVE_PRODUCTION — Referenzdesign  
2. **CRM** — `projects/crm` — FastAPI/Jinja/HTMX — ACTIVE_PRODUCTION — schwarze Sidebar, „W“-Mark  
3. **Lead Creator** — `projects/B2B-Kundenfänger…` — Flask — ACTIVE_PRODUCTION — leads.*  
4. **Preview Studio** — Cockpit-Modul + agency-web Duplikat — braunes Dark-Gold  
5. **Login-Seiten** — Cockpit Login, CRM `auth/login.html`, Admin/Shop Logins, Leads Basic-Auth

### Priorität B

- Nils UI, Jarvis (Cockpit + jay.html Legacy), Kalkulator (Cockpit), Abrechnung (Cockpit), Akquise-Freigabe/Report, Workorders, Sales-Dashboard (LEGACY), Angebote/Abrechnung-Pfade, Agency Setup

### Priorität C

- SHY001 Portal/Admin/Konto (Kundenbranding behalten)  
- Onboarding, B2B Portal, TourMeter, Radar UI, GGG Content, Voice Demo

## Externe Dienste (nicht umgestalten)

n8n · Cal.com · DocuSeal · Umami · Retell AI · Placetel · Meta Business · Google (GBP/Gmail/Drive) · (optional Cisco Webex falls später)

## Legacy- & Dubletten-Kandidaten

| ID | Konflikt |
|----|----------|
| preview-studio-cockpit vs preview-studio-agency-web | zwei Preview Studios, gleiches braunes UI |
| sales-pipeline-legacy vs Cockpit Pipeline vs CRM Pipeline | drei Pipeline-Oberflächen |
| jay.html vs Cockpit Jarvis | Assistent doppelt |
| flask-contacts (Shop) vs projects/crm | unterschiedliche SoR — **nicht** zusammenwerfen |
| landingpage-manager | GHL EOL |
| Logo-Dateien horizontal/icon vs freigestellte Wortmarke | siehe brand-assets |

## Lead Creator (Detail)

| Feld | Wert |
|------|------|
| Anzeigename | DHK Leads / B2B-Kundenfänger |
| Intern | dhk-leads |
| Repo | `projects/B2B-Kundenfänger für Digitale Handwerkskunst/` |
| Verzeichnis Dashboard | `dashboard/` (`app.py`, Jinja, `style.css`) |
| Funktionen | OSM/Google Places Scan, Scoring, CSV Import/Export, Auswertung, DSGVO-Purge CLI |
| Datenquelle | `leads.db` SQLite |
| Zielsystem | internes Research (kein Auto-Kontakt); CRM-Import separat möglich |
| Auth | Dashboard User/Pass (Env) |
| Branding | `#E8600A`, warme Grautöne, **eigenes SVG-Wortmark**, nicht `/ci/webschmiede-logo.png` |
| Status | ACTIVE_PRODUCTION (Memory 2026-07-26) |
| Deploy | `deploy_dhk_leads.py` im Server-Repo |

**Empfehlung:** Als führendes Lead-Research-Tool in Tool-Registry führen. Nicht mit CRM-Import oder Akquise-Freigabe zusammenführen, bevor Unterschiede dokumentiert und freigegeben sind.

## Server-Rollen / Compose (Shared Infra)

| Stack | Ort | Hinweis |
|-------|-----|---------|
| snack-api | systemd Gunicorn :8000 | Haupt-API, kein Root-Compose |
| n8n | /opt/n8n (+ override compose) | Automation |
| Cal.com | infra/calcom/docker-compose.yml | Termine |
| Voice demo | infra/voice-demo/ | Demo |
| Umami / DocuSeal | /opt/* | OSS |
| CRM | Docker compose in `projects/crm` | :8090 |
| DHK Leads | Docker compose im Leads-Repo | :5099 |

## Domains (Nginx, Stand Audit 2026-07-24 + Docs)

digitalehandwerkskunst.de · analytics.* · cal.* · radar.* · sign.* · voice.* · kunde-muster.* · kunde-yassine.* · snackhouse-yassine.de · leads.* · crm.*

## Sicherheitsstatus (nur belegt)

- Agency/Admin 2FA + Rate-Limit dokumentiert (Memory 2026-07-28)  
- Secrets in `deploy.secrets.local` / Server-Env — **nicht** in Registry  
- Tenant-Isolation Agency ≠ Kunde — Regel `.cursor/rules/tenant-isolation.mdc`

## Lücken / UNKNOWN

- Uptime Kuma: **nicht** im Repo gefunden → UNREACHABLE (Ops-Guardian ersetzt Monitoring-Idee)  
- radar.* UI-Branding nicht lokal vollständig gelesen  
- b2b-portal / sales-angebot Branding: Code vorhanden, Designaudit ausstehend  
- Live `docker ps` / systemd in diesem Schritt nicht neu SSH-geprüft
