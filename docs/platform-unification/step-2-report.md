# Step 2 Report — Shared Design System

**Datum:** 2026-08-02  
**Branch:** `docs/platform-unification-inventory`  
**Ausgang:** `334182e` (INVENTORY_COMPLETE)  
**Production-Deploy:** nein  
**Anwendungsmigration:** nein

## Urteil

**DESIGN_SYSTEM_READY** — mit dokumentierten Einschränkungen (siehe unten).

## Was geliefert wurde

| Liefergegenstand | Ort |
|------------------|-----|
| Kanonische Brand Assets + Manifest | `app/static/brand/webschmiede/` |
| Design Tokens | `app/static/ci/webschmiede-tokens.css` |
| CSS-Architektur | `webschmiede-{base,layout,components,utilities,app}.css` |
| CI-Bridge (deprecated Hinweis) | `webschmiede-ci.css` importiert Tokens |
| UI JS | `webschmiede-ui.js` |
| Jinja Macros | `app/backend/templates/shared/ui/macros.html` |
| Showcase | `/design-system` (APP_ENV local/staging/test) |
| AppShell Prototyp | `/design-system/appshell` |
| BrandConfig | `app/backend/brand_config.py` + `config/branding.example.yaml` |
| Icons | `config/ui_icons.yaml` (Font Awesome 6) |
| Tool Registry Schema | `config/platform_registry.example.yaml` + Validator |
| Design Lint | `scripts/design_lint.py` + Allowlist |
| Tests | `app/backend/scripts/test_design_system.py` (15 OK) |
| Evidence Screenshots | `docs/platform-unification/evidence/` |

## Preflight (ergänzt)

| Ziel | Ergebnis |
|------|----------|
| Agency Cockpit Login | erreichbar, Titel „Agency Admin – Webschmiede“, Logo Mark + Orange `#FF6600`, Login erforderlich → Screenshot `preflight/agency-cockpit-login.png` |
| CRM Login | erreichbar `crm…/login`, Titel „Login · Webschmiede“, **oranges W**, Canvas `#F7F5F2` → `preflight/crm-login.png` |
| Lead Creator | `leads…` antwortete ohne DOM (vermutlich HTTP Basic / Challenge) — als ACTIVE belassen, UI-Baseline lokal aus Templates |
| Design System lokal | `127.0.0.1:8765` Showcase + AppShell Baselines |

## Einschränkungen / Risiken

1. **SVG-Logos fehlen** — bewusst nicht neu gezeichnet; PNG kanonisch.  
2. Flask-Route `/ci/<path>` kann lokal mit Nginx kollidieren — in Prod liefert Nginx Static; Blueprint-Route ist Fallback.  
3. CRM-/Cockpit-Migration **nicht** begonnen (Soll SCHRITT 3).  
4. Mobile Viewport-Baselines nur manuell/DevTools empfohlen; Desktop-Baselines committed.  
5. Lead Creator Live-Screenshot unvollständig (Auth-Gate).

## Nachweis keine Geschäftslogik / keine Migration

- Keine CRM Template-Umstellung  
- Keine Änderungen an Pipeline/Leads/Deals-Services  
- Keine DB-Migration  
- Showcase nur synthetische Demo-Daten  
- Production: `/design-system` → 404

## Performance (Kurz)

| Datei | ~Größe |
|-------|--------|
| webschmiede-tokens.css | klein |
| webschmiede-app.css (Imports) | modular |
| logo-mark.png | ~316 KB (CI Original) |
| favicon.png | Resize 32px |
| app-icon-512.png | Resize |

Kein zusätzliches JS-Framework. Font: bestehendes Bunny Inter.

## SCHRITT 3 Umfang (exakt)

1. CRM Login → LoginCard + kanonisches Logo  
2. CRM AppShell → helle Sidebar + BrandLockup  
3. CRM Dashboard → Tokens/Components  
4. Cockpit Tab „Werkzeuge“ aus Registry (ohne Vendor-Secrets)  
5. Staging-Abnahme Desktop/Mobile + Regression CRM fachlich unverändert  

## Rollback

```text
git checkout docs/platform-unification-inventory~1 -- app/static/ci app/static/brand/webschmiede app/backend/design_system.py app/backend/brand_config.py app/backend/templates config/scripts
# oder gesamten Step-2-Commit reverten
# Design-System-Routen: APP_ENV=production → bereits 404
```
