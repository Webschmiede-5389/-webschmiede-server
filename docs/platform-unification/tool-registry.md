# Tool Registry

**Status:** Schema + Seed spezifiziert · Cockpit-UI „Werkzeuge“ noch nicht gebaut

## Ziel

Zentrale, mandantenfähige Liste aller Systeme. Speist den Cockpit-Bereich **Werkzeuge** (oder „Systeme & Werkzeuge“).  
**Keine Secrets.** Keine hardcodierten Link-Duplikate in vielen Templates.

## Schema `ToolRegistryEntry`

| Feld | Typ | Pflicht |
|------|-----|---------|
| id | string | ja |
| slug | string | ja |
| display_name | string | ja |
| short_description | string | ja |
| category | enum | ja |
| icon | string (FA class oder /ci path) | ja |
| environment | production \| staging \| local | ja |
| service_type | dashboard \| portal \| automation \| vendor \| docs \| calc | ja |
| internal_or_external | internal \| external | ja |
| base_url | https URL oder path | ja |
| healthcheck_url | URL \| null | nein |
| open_mode | same_tab \| new_tab | ja |
| required_roles | string[] | ja |
| tenant_visibility | agency \| all_customers \| customer_ids[] | ja |
| customer_visibility | boolean | ja |
| status | inventory status enum | ja |
| sort_order | int | ja |
| branding_mode | AGENCY_INTERNAL \| … | ja |
| owner | string | ja |
| documentation_url | string \| null | nein |
| active | boolean | ja |
| created_at / updated_at | ISO8601 | ja |

### Kategorien

Vertrieb · CRM · Kundenverwaltung · Kommunikation · Content & Social Media · Leadgewinnung · Automatisierung · Website & Funnel · Angebote & Abrechnung · KI & Assistenten · Betrieb & Monitoring · Administration · Externe Dienste · Entwicklung & Staging

## Speicherort (Vorschlag)

```
agency/tool-registry.json          # git-tracked, keine Secrets
app/backend/tool_registry.py       # load + RBAC filter (SCHRITT 2/3)
GET /api/agency/tools              # auth required
```

Agency Hub Cards später aus derselben Datei speisen (eine Quelle).

## Seed (Auszug — aktiv für Registry)

| id | Name | Kategorie | URL | Env | open | roles |
|----|------|-----------|-----|-----|------|-------|
| agency-cockpit | Agency Cockpit | Administration | /agency | production | same | agency |
| crm | CRM | CRM | https://crm.digitalehandwerkskunst.de | production | new_tab | agency |
| lead-creator-dhk | Lead Creator (DHK Leads) | Leadgewinnung | https://leads.digitalehandwerkskunst.de | production | new_tab | agency |
| preview-studio | Preview Studio | Website & Funnel | /agency (tab) | production | same | agency |
| kalkulator | Kalkulator | Angebote & Abrechnung | /agency | production | same | agency |
| nils | Nils Ops | KI & Assistenten | /nils | production | new_tab | agency |
| agency-hub | Agency Hub | Administration | /agency-hub | production | new_tab | agency |
| n8n | n8n | Automatisierung | /n8n/ | production | new_tab | agency_admin |
| calcom | Cal.com | Kommunikation | https://cal.digitalehandwerkskunst.de | production | new_tab | agency |
| docuseal | DocuSeal | Angebote & Abrechnung | https://sign.digitalehandwerkskunst.de | production | new_tab | agency |
| umami | Umami | Betrieb & Monitoring | https://analytics.digitalehandwerkskunst.de | production | new_tab | agency_admin |
| retell | Retell AI | Externe Dienste | vendor URL | production | new_tab | agency_admin |
| placetel | Placetel | Externe Dienste | vendor URL | production | new_tab | agency_admin |
| meta | Meta Business | Externe Dienste | vendor | production | new_tab | agency_admin |
| shy001-admin | SHY001 Admin | Kundenverwaltung | snackhouse admin URL | production | new_tab | agency + customer_ops |
| tourmeter | TourMeter | Entwicklung & Staging | /transport-kalkulator.html | production | new_tab | agency |
| sales-dashboard-legacy | Sales Dashboard (Legacy) | Vertrieb | /sales-dashboard.html | production | new_tab | agency | warn legacy |

Externe Vendor-URLs in Registry nur als erlaubte Allowlist-Hosts.

## RBAC / Sichtbarkeit

- Normale Agency-Nutzer: keine Admin-only Vendor-Links (n8n Admin, Umami, Retell)  
- Staging-Einträge nur mit Rolle `agency_admin` oder Env Badge + Staging-Session  
- Kundenrollen sehen nur `customer_visibility` Tools ihres Tenants  
- Keine Tokens in Query-Parametern

## UI im Cockpit

Neuer Nav-Punkt **Werkzeuge** → Liste/Karten aus API:

- Name, Kurzbeschreibung, Icon (CI Mark oder FA)  
- EnvironmentBadge, Status, System, Link  
- Warnung bei LEGACY / EXPERIMENTAL  
- HealthStatus wenn `healthcheck_url` gesetzt und Cache ok

Healthchecks: optional, async, nie Secrets loggen.
