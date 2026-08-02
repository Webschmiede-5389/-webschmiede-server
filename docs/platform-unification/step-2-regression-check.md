# Step-2 Regression Check (vor CRM Branding-Pilot)

**Datum:** 2026-08-02  
**Basis-Commit:** `53b39fb` (`feat(design-system): shared WebSchmiede tokens, AppShell lab, brand assets`)  
**Pilot-Branch:** `feature/platform-unification-branding-pilot`

## Ergebnis

**BESTANDEN** — keine unbeabsichtigte Beeinflussung bestehender Production-Oberflächen durch Schritt 2. CRM-Migration darf starten.

## 1. Blueprint-Registrierung (`main.py`)

| Prüfung | Ergebnis |
|---------|----------|
| `/design-system` in Production (`APP_ENV=production`) | 404 / Gate aus (`design_system_enabled() is False`) |
| Bestehende Routes überschrieben? | Nein — eigener Blueprint, eigene Pfade |
| Öffentliche Auth-Oberfläche zusätzlich? | Nein — Lab ist HTML-Showcase ohne Login-Änderung |
| Importfehler ohne DS-Deps? | Nein — Standard-Flask + Templates/CSS im Repo |
| Startzeit | Blueprint-Register vernachlässigbar |
| Unerwartete Prod-Registrierung Lab-Seiten | Lab-Routen registriert, aber `before_request` → 404 in Prod |

Brand-/CI-Static-Routen (`/brand/webschmiede/*`, `/ci/*`) bleiben über Blueprint erreichbar (gleiche Klasse wie bisherige CI-Logos).

## 2. `webschmiede-ci.css` (Tokens-Import)

**Verbraucher (Repo-Suche):** CI-Vorlagen unter `app/static/ci/*-vorlage.html`, `agency-hub.html`, Docs unter `docs/platform-unification/*`.

| Prüfung | Ergebnis |
|---------|----------|
| Zyklische Imports | Nein (`ci` → `tokens` einmalig) |
| Doppelte Token-Ladung durch Lab | Lab nutzt `webschmiede-app.css`, nicht parallel `ci`+`app` doppelt in Templates |
| Relative Pfade | `@import url("./webschmiede-tokens.css")` — gültig |
| Visuelle Regression CI-Docs | Tokens spiegeln BRAND.md-Orange `#FF6600`; kein Gold `#C9A84C` in Tokens |
| Fehlende Assets | Brand-Manifest vorhanden; SVG absichtlich `MISSING_NO_REDRAW` |

Hinweis: CI-Print-Vorlagen behalten ggf. Legacy-Gold in eigener CSS — **nicht** durch Tokens erzwungen. Design-Lint allowlist dokumentiert Altlasten.

## 3. Static-Routing

| Ebene | Status |
|-------|--------|
| Flask lokal | `/ci/`, `/brand/webschmiede/` via Design-System-Blueprint |
| FastAPI CRM | `/static/ws/...` nach Sync (kein Nginx nötig lokal) |
| Nginx Production | Unverändert in diesem Schritt (kein Deploy) |
| Cache-Busting Pilot | Query `?v=pilot3` in CRM-Links |
| MIME | CSS/JS/PNG Standard |

## 4. Automatisierte Regression

- `python -m unittest app.backend.scripts.test_design_system` → **15 OK**
- `design_system_enabled()` mit `APP_ENV=production` → **False**

## Freigabe für Schritt 3

CRM und Agency-Werkzeuge dürfen das zentrale Designsystem einbinden, ohne Schritt 2 zurückzurollen.
