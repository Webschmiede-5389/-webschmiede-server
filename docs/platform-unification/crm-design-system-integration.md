# CRM Design-System-Integration

**Mode:** kontrollierter Sync mit Prüfsumme (Option 3 der Vorgabe)  
**Kein** paralleles CRM-Token-Set, kein CDN für Markenassets, kein Symlink.

## Quellpfad (SoT)

`webschmiede-server/app/static/ci/`  
`webschmiede-server/app/static/brand/webschmiede/`

## Zielpfad (CRM)

`projects/crm/app/static/ws/ci/`  
`projects/crm/app/static/ws/brand/webschmiede/`  
`projects/crm/app/static/ws/VERSION.yaml` (SHA-256 je Datei + `source_commit`)

## Sync-Befehl

```bash
python scripts/sync_design_system_to_crm.py --source-commit 53b39fb
# optional: --crm-root ../crm
```

## Ladefolge (CRM HTML)

1. Bunny Fonts Inter  
2. Font Awesome 6.5 (Icons laut `config/ui_icons.yaml`)  
3. `/static/ws/ci/webschmiede-app.css?v=pilot3` (Tokens → Base → Layout → Components → Utilities)  
4. `/static/css/crm.css?v=pilot3` (AppShell-Overrides, Formulare, KPI — referenziert Token-Farben `#FF6600`)

## BrandConfig CRM

`app/branding.py` — Mode `AGENCY_INTERNAL`, feste Namen/Pfade, kein freies CRM-Orange.

Inject via `app/jinja_compat.py` → `ws_brand` in jedem TemplateResponse.

## Cache Busting

Query `?v=pilot3` + Service-Worker Cache-Name `ws-crm-v3-pilot`.

## Rollback

1. CRM: `git checkout` der Templates/`crm.css`/`sw.js`/`manifest`/`jinja_compat`/`branding.py`  
2. Optional: Ordner `app/static/ws/` entfernen  
3. Agency: Werkzeuge-Nav + `platform_tools` / Registry zurücknehmen

## Deployment-Auswirkung

Kein Production-Deploy in SCHRITT 3. Staging/local: CRM muss `static/ws` mitdeployen (Datei-Kopie, kein Shared-Volume mit Agency-Container).
