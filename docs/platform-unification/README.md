# Platform Unification — README

**Stand:** 2026-08-02  
**Scope:** AGENCY + SHARED_INFRA (+ Hub-Sibling-Projekte read-only)  
**Aktueller Schritt:** SCHRITT 1 — nur Analyse (kein Production-Deploy, keine Geschäftslogik-Änderung)

## Gesamturteil (Zwischenstand)

| Gate | Status |
|------|--------|
| **INVENTORY_COMPLETE** | **JA** |
| **DESIGN_SYSTEM_READY** | **JA** (SCHRITT 2 — Lab/Tokens/AppShell; keine App-Migration) |
| BRANDING_PILOT_READY | NEIN — Pilot CRM+Werkzeuge = SCHRITT 3 |
| PLATFORM_UNIFICATION_STAGING_READY | NEIN |
| PRODUCTION_CUTOVER_READY | NEIN |

Siehe [step-2-report.md](./step-2-report.md).

## Was diese Ordner enthält

| Datei | Inhalt |
|-------|--------|
| [application-inventory.md](./application-inventory.md) | Lesbare Anwendungsliste |
| [application-inventory.json](./application-inventory.json) | Maschinenlesbare Inventur |
| [brand-assets.md](./brand-assets.md) | Logo-/Asset-Audit + kanonische Struktur |
| [design-audit.md](./design-audit.md) | Extrahierte Ist-Werte Cockpit vs. Website vs. CRM |
| [design-system.md](./design-system.md) | Shared CSS Einstieg |
| [design-tokens.md](./design-tokens.md) | Token-Tabelle |
| [component-library.md](./component-library.md) | Komponenten + Macros |
| [app-shell.md](./app-shell.md) | AppShell Prototyp |
| [branding-modes.md](./branding-modes.md) | Branding-Modi |
| [icon-system.md](./icon-system.md) | Font Awesome Mapping |
| [tool-registry.md](./tool-registry.md) | ToolRegistry Schema |
| [navigation-map.md](./navigation-map.md) | Cross-Linking-Soll |
| [migration-matrix.md](./migration-matrix.md) | Priorität A/B/C |
| [customer-branding.md](./customer-branding.md) | Branding-Modi Detail |
| [new-project-guidelines.md](./new-project-guidelines.md) | Neue Apps |
| [visual-test-plan.md](./visual-test-plan.md) | Screenshots |
| [accessibility.md](./accessibility.md) | A11y Smoke |
| [security.md](./security.md) | Toolübersicht Sicherheit |
| [staging-rollout.md](./staging-rollout.md) | Staging-Plan |
| [production-cutover-checklist.md](./production-cutover-checklist.md) | Cutover |
| [step-2-report.md](./step-2-report.md) | SCHRITT 2 Abschluss |
| `evidence/` | Baseline- und Preflight-Screenshots |

## Visuelle Referenz (kanonisch)

**Agency Cockpit** (`app/static/agency.html` → `/agency`):

- Weiß / hellgrau Hintergrund
- Helle Sidebar
- Offizielles Logo-Mark + „WebSchmiede“ / „Digitale Handwerkskunst“
- Primärakzent `#FF6600`

**Nicht** als Agency-Referenz:

- Snack-House-Gold `#C9A84C` / braune Dark-Themes (Kundenportal + Legacy Preview Studio / Sales Dashboard)
- CRM-Schwarz-Sidebar + orangener „W“-Platzhalter

## Lead Creator (gefunden)

**Name im Bestand:** DHK B2B-Kundenfänger / Leads Dashboard  
**Repo:** `My_Company_Hub/projects/B2B-Kundenfänger für Digitale Handwerkskunst/`  
**Prod:** `https://leads.digitalehandwerkskunst.de`  
**Lokal:** `http://localhost:5099` (`python cli.py dashboard`)

## Bestehendes CI-CSS (nicht neu erfinden)

`app/static/ci/webschmiede-ci.css` + `docs/agency/ci/BRAND.md` sind die Seed-Quelle.  
Ziel: daraus ein **App-Shell**-fähiges Shared-Paket ableiten — **keine zweite parallele Bibliothek**.

## Nächste Schritte (SCHRITT 3)

1. CRM Login + AppShell + Dashboard auf Shared CSS/Partials (Staging)  
2. Cockpit-Tab Werkzeuge aus `platform_registry`  
3. Kein Production-Cutover ohne Freigabe

## Lab starten

```bash
set APP_ENV=local
python -c "..."  # siehe step-2-report / design_system Blueprint in snack-api
# oder snack-api mit APP_ENV=local → http://127.0.0.1:8000/design-system
```

## Grenzen (verbindlich)

- Kein Production-Deploy in diesem Auftrag  
- Keine CRM-Lifecycle-/Lead-/Deal-Logik ändern  
- Keine echten Kundenmails / WhatsApp / Käufe  
- Agency-Web Publish nur nach expliziter Freigabe Christian  
- Externe UIs (n8n, Cal.com, Retell, Meta, Google, Placetel, DocuSeal, Umami) nicht umbauen
