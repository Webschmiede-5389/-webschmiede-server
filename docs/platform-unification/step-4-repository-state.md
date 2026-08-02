# Step 4 — Repository State

**Datum:** 2026-08-02  
**Stash angefasst:** nein

## Server (`webschmiede-server`)

| Feld | Wert |
|------|------|
| Branch | `feature/platform-unification-branding-pilot` |
| HEAD | `6987fa8` |
| Parent Designsystem | `53b39fb` |
| Stash (unangetastet) | `stash@{0}: wip-before-branding-pilot-step3` (+ ältere Stashes) |

### Pilot committed (6987fa8)

`platform_registry.yaml`, `platform_registry.py`, `platform_tools.py`, `test_platform_registry.py`, `agency.html` (Werkzeuge), `main.py` (+9 Zeilen Register), Sync-/Validate-Scripts, Step-3 Docs.

### Fremde WIP (uncommitted, nicht anfassen)

Zahlreiche `M`/`??` unter agency-web, admin, Nils, `_*.py`, docs/kunden, voice-agent, u. a. — **nicht** Teil des Piloten.

### Memory

`docs/memory/CURRENT.md` ggf. lokal geändert — kein Pflicht-Teil von 6987fa8.

## CRM (`projects/crm`)

| Feld | Wert |
|------|------|
| Branch | `feature/platform-unification-branding-pilot` |
| HEAD | `3276689` |
| Pre-Pilot Parent (A/B) | `ee1da86` (nicht Server-`53b39fb`) |
| Stash | keiner relevant für diesen Branch |

### Pilot committed (3276689)

`branding.py`, `jinja_compat.py`, `base.html`, `login.html`, `crm.css`, `sw.js`, `manifest.webmanifest`, `app/static/ws/**`.

### Fremde WIP (untracked, nicht anfassen)

`docs/pol001-*`, `infra/`, `mobile/`, viele `scripts/_*.py`, staging-scripts, u. a.

## Trennbarkeit

Pilot vs. Fremd: **sicher trennbar**. Pilot vollständig committed. Fremde WIP unangetastet. Stash nicht applied/gelöscht.
