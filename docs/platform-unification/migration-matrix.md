# Migration Matrix

**Stand:** 2026-08-02 · Nur Planung

## Priorität A

### Agency Cockpit

| | |
|--|--|
| Ist | Light Orange Referenz, Preview-Insel braun |
| Soll | Referenz bleiben; Preview restylen; Tab Werkzeuge |
| Reuse | Sidebar, panels, login, tokens |
| Risiken | große agency.html Datei; Regression Tabs |
| Screens | Login, Übersicht, Pipeline, Werkzeuge, Preview |
| Aufwand | M (Werkzeuge+Preview) |
| Abhängigkeiten | Tool-Registry, Shared CSS |

### CRM

| | |
|--|--|
| Ist | Schwarze Sidebar, W-Mark, warme Canvas |
| Soll | Helle AppShell wie Cockpit, offizielles Logo, Unterzeile Digitale Handwerkskunst, gleiche Buttons/Formulare/Tabellen/Badges |
| Reuse | crm.css Tokens schon nah an Orange; HTMX Flows unverändert |
| Risiken | Mobile-Bar, Handwerk-Inquiry Modus, PWA Manifest Icons |
| Regression | Alle CRM-Module dürfen funktional nicht wegfallen |
| Screens | Login, Dashboard, Unternehmen-Liste, Formular, Empty, Error, Mobile |
| Aufwand | L |
| Abhängigkeiten | Shared Tokens, Logo Static-Pfad |

### Login-Seiten (zentral)

| | |
|--|--|
| Ist | Cockpit gut; CRM „A“-Mark; Shop dunkel-gold; Leads Basic |
| Soll | LoginCard Shared für Agency/CRM/Leads |
| Risiken | Auth-Flows nicht anfassen außer Markup/CSS |
| Aufwand | M |

### Toolübersicht

| | |
|--|--|
| Ist | Agency Hub Card-Grid (hardcoded) |
| Soll | Registry-getrieben im Cockpit |
| Aufwand | M |

### Preview Studio

| | |
|--|--|
| Ist | Braun/Gold Dark, Emoji |
| Soll | Agency Light Chrome; iframe Inhalt darf Kundenfarben zeigen |
| Duplikat | agency-web Page vs Cockpit — führend: **Cockpit**, agency-web angleichen oder deprecaten |
| Aufwand | M |

### Lead Creator

| | |
|--|--|
| Ist | Warm Orange `#E8600A`, SVG Eigenlogo |
| Soll | Tokens + Logo CI; Link zurück Cockpit; Tool-Registry |
| Funktionen | Scan/Export unverändert |
| Aufwand | M |

## Priorität B

| App | Ist | Soll | Aufwand | Risiko |
|-----|-----|------|---------|--------|
| Nils UI | unbekannt/mixed | AppShell light | M | Ops-Regression |
| Jarvis | Cockpit ok / jay legacy | Legacy deprecaten | S | — |
| Kalkulator / Abrechnung | Cockpit panels | Token-Konsistenz | S | — |
| Akquise Freigabe/Report | mixed | Light Agency | M | Auth |
| Sales Dashboard | brown legacy | deprecaten → CRM/Cockpit | S | Nutzer-Bookmark |
| CI Templates | schon orange | behalten | — | — |
| Agency Setup | aligned | Token sync | S | Secrets UI |

## Priorität C

| App | Hinweis |
|-----|---------|
| SHY001 Portal/Admin | CUSTOMER branding — Agency Shell nur für „powered by“ optional |
| Onboarding | gemischt |
| TourMeter | experimental |
| Radar / Voice / GGG | UNKNOWN — erst Inventur vertiefen |
| Landingpage-manager | EOL, nicht migrieren |

## Pilotumfang (SCHRITT 3) — verbindlich eng

1. CRM Login (visuell)  
2. CRM AppShell (Sidebar hell + Logo)  
3. CRM Dashboard  
4. Cockpit Toolübersicht (Registry)

**Nicht** im Pilot: Pipeline-Logik, Placetel, Import, Meta-Webhooks, Production-Deploy.

## Umsetzungsaufwand gesamt (Schätzung)

| Phase | Inhalt |
|-------|--------|
| SCHRITT 1 | Analyse Docs — **dieser Commit** |
| SCHRITT 2 | Shared CSS/Partials/Tests — M |
| SCHRITT 3 | Pilot CRM+Tools Staging — L |
| SCHRITT 4 | Abnahme — M |
| SCHRITT 5 | Preview, Leads, Nils, … — L–XL |
