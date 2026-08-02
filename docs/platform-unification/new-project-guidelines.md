# New Project Guidelines

Neue **interne** Anwendungen starten mit dem Shared Design System (SCHRITT 2).

## Pflicht

- [ ] Assets aus `/brand/webschmiede/` (Manifest)  
- [ ] CSS: `/ci/webschmiede-app.css`  
- [ ] Root-Wrapper `class="ws-app"`  
- [ ] BrandLockup Macro / Markup  
- [ ] AppShell-Pattern (oder Showcase als Vorlage)  
- [ ] EnvironmentBadge  
- [ ] Icons laut `config/ui_icons.yaml` (Font Awesome 6)  
- [ ] Eintrag in Tool Registry (Beispiel: `config/platform_registry.example.yaml`)  
- [ ] Keine hart codierten Markenfarben (`#FF6600` nur über Tokens)  
- [ ] Keine Logo-Duplikate außerhalb `/brand/webschmiede` bzw. `/ci` Quelle  
- [ ] Kein `#C9A84C` / `#E8600A` in Agency-Shells  
- [ ] `python scripts/design_lint.py` grün für neue Dateien  

## Lab

`/design-system` und `/design-system/appshell` nur mit `APP_ENV=local|staging|test`.

## Kundenportale

Nur BrandConfig / Tenant-Tokens — siehe [branding-modes.md](./branding-modes.md).
