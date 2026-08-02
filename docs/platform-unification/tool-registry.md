# Tool Registry

**Status SCHRITT 3:** reale Datei `config/platform_registry.yaml` + Loader + Cockpit-UI „Werkzeuge“ + Validator/Tests.

## Dateien

- `config/platform_registry.yaml` (produktiv für Cockpit-API, nur bestätigte URLs)
- `config/platform_registry.example.yaml` (Schema-Beispiel)
- `app/backend/platform_registry.py` (fail-closed Load/Filter)
- `app/backend/platform_tools.py` → `GET /api/agency/tools`
- `scripts/validate_platform_registry.py`
- `app/backend/scripts/test_platform_registry.py`

```bash
python scripts/validate_platform_registry.py config/platform_registry.yaml
python -m unittest app.backend.scripts.test_platform_registry -v
```

## Ziel

Zentrale Liste aller Systeme. Speist den Cockpit-Bereich **Werkzeuge**.  
**Keine Secrets.** Keine hardcodierten Link-Duplikate in vielen Templates.

## Schema `ToolRegistryEntry`

| Feld | Typ | Pflicht |
|------|-----|---------|
| id | string | ja |
| slug | string | ja |
| display_name | string | ja |
| short_description | string | ja |
| category | string (s. Kategorien) | ja |
| icon | string (FA key aus ui_icons.yaml) | ja |
| environment | production \| staging \| local | ja |
| service_type | string | ja |
| internal_or_external | internal \| external | ja |
| base_url | https URL oder path | ja |
| healthcheck_url | URL \| null | nein |
| open_mode | same_tab \| new_tab | ja |
| required_roles | string[] | ja |
| tenant_visibility | agency \| … | ja |
| status | enum | ja |
| sort_order | int | ja |
| branding_mode | AGENCY_INTERNAL \| … | ja |
| owner | string | ja |
| active | bool | ja |

## Kategorien (UI)

Zentrale · Vertrieb · Leads · CRM · Kunden · Kommunikation · Content · Automatisierung · Dokumente · Betrieb · Externe Dienste · Entwicklung & Staging

## Reale Einträge (SCHRITT 3)

| ID | URL | Env | Rollen |
|----|-----|-----|--------|
| agency-cockpit | https://digitalehandwerkskunst.de/agency | production | agency |
| agency-hub | https://digitalehandwerkskunst.de/agency-hub | production | agency |
| crm | https://crm.digitalehandwerkskunst.de | production | agency |
| dhk-leads | https://leads.digitalehandwerkskunst.de | production | agency |
| agency-setup | https://digitalehandwerkskunst.de/agency-setup | production | agency_admin |
| nils | https://digitalehandwerkskunst.de/nils | production | agency |
| n8n | https://digitalehandwerkskunst.de/n8n/ | production | agency_admin |
| calcom | https://cal.digitalehandwerkskunst.de | production | agency |
| docuseal | https://sign.digitalehandwerkskunst.de | production | agency |
| umami | https://analytics.digitalehandwerkskunst.de | production | agency_admin |
| ci-docs | https://digitalehandwerkskunst.de/ci/ | production | agency |
| design-system-lab | /design-system | staging | agency_admin |

Nicht aufgenommen ohne bestätigte sichere URL: Retell, Placetel-Admin, Meta Business, Google-Konsolen, Jarvis-Tab ohne eigene URL, Preview-Studio-Duplikat.

## RBAC / Sichtbarkeit

- Production-Viewer sieht keine Staging/Local-Einträge
- `agency` sieht keine `agency_admin`-only Tools
- `agency_admin` impliziert `agency`
- Ungültige URL → Karte übersprungen (Seite bleibt)
- Registry-Strukturfehler → API 503 fail-closed

## UI im Cockpit

Nav **Werkzeuge** → Suche, Kategorie, Environment, ToolCards, External `noopener noreferrer`.  
Deep-Link: `/agency#tools`.

## Inventur-Hinweise (SCHRITT 1)

Vollständige Kandidatenliste: `application-inventory.md`. Vendor ohne confirmed Link bleiben draußen.
