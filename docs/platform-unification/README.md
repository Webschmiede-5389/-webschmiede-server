# Platform Unification — README

**Stand:** 2026-08-02  
**Scope:** AGENCY + SHARED_INFRA (+ Hub-Sibling-Projekte read-only)  
**Aktueller Schritt:** SCHRITT 1 — nur Analyse (kein Production-Deploy, keine Geschäftslogik-Änderung)

## Gesamturteil (Zwischenstand)

| Gate | Status |
|------|--------|
| **INVENTORY_COMPLETE** | **JA** (lokal/dokumentiert; Live-HTTP-Spotcheck separat) |
| DESIGN_SYSTEM_READY | NEIN — Tokens/AppShell spezifiziert, Shared-Paket noch nicht gebaut |
| BRANDING_PILOT_READY | NEIN — Pilot (CRM Login/Shell/Dashboard + Werkzeuge) noch nicht umgesetzt |
| PLATFORM_UNIFICATION_STAGING_READY | NEIN |
| PRODUCTION_CUTOVER_READY | NEIN — bewusst, Freigabe fehlt |

## Was diese Ordner enthält

| Datei | Inhalt |
|-------|--------|
| [application-inventory.md](./application-inventory.md) | Lesbare Anwendungsliste |
| [application-inventory.json](./application-inventory.json) | Maschinenlesbare Inventur |
| [brand-assets.md](./brand-assets.md) | Logo-/Asset-Audit + kanonische Struktur |
| [design-audit.md](./design-audit.md) | Extrahierte Ist-Werte Cockpit vs. Website vs. CRM |
| [design-system.md](./design-system.md) | Ziel-Tokens + Komponenten-Katalog (Spezifikation) |
| [tool-registry.md](./tool-registry.md) | ToolRegistryEntry-Schema + Seed-Liste |
| [navigation-map.md](./navigation-map.md) | Cross-Linking-Soll |
| [migration-matrix.md](./migration-matrix.md) | Priorität A/B/C |
| [customer-branding.md](./customer-branding.md) | Branding-Modi 1–5 |
| [new-project-guidelines.md](./new-project-guidelines.md) | Neue interne Apps / Kundenportale |
| [visual-test-plan.md](./visual-test-plan.md) | Referenzscreens + Checks |
| [security.md](./security.md) | Toolübersicht / Cross-Link Sicherheit |
| [staging-rollout.md](./staging-rollout.md) | Staging-Plan |
| [production-cutover-checklist.md](./production-cutover-checklist.md) | Cutover nur nach Freigabe |

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

## Nächste Schritte (SCHRITT 2)

1. Shared Tokens + CSS (oder CRM-kompatible Token-Datei) aus BRAND + Cockpit ableiten  
2. AppShell / BrandHeader / LoginCard Spezifikation in Code (noch ohne flächige Migration)  
3. Tool-Registry JSON + Cockpit-Tab „Werkzeuge“ (Pilot)  
4. Dann SCHRITT 3: nur CRM Login + Shell + Dashboard

## Grenzen (verbindlich)

- Kein Production-Deploy in diesem Auftrag  
- Keine CRM-Lifecycle-/Lead-/Deal-Logik ändern  
- Keine echten Kundenmails / WhatsApp / Käufe  
- Agency-Web Publish nur nach expliziter Freigabe Christian  
- Externe UIs (n8n, Cal.com, Retell, Meta, Google, Placetel, DocuSeal, Umami) nicht umbauen
