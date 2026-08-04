# Post-Merge Branding-UI — Scope Guard (read-only snapshot)

At: 2026-08-04T06:15:00Z (local approx)

## Zielbranches
| Repo | Zielbranch | Vorher | Soll |
|------|------------|--------|------|
| CRM | `feature/platform-unification-branding-pilot` | `81398b4` | enthält `68ede4d` |
| Server | `feature/platform-unification-branding-pilot` | bereits `22a550a` HEAD | unverändert belassen |

## Branding-UI (CRM 68ede4d) — erlaubt
- app/static/css/crm.css
- app/templates/companies/archived.html
- app/templates/dashboard/index.html
- app/templates/leads/list.html
- app/templates/tasks/list.html
- app/templates/vertrieb/anrufliste.html
- tests/test_branding_ui_layout.py

## Evidence / Prüfscripts (Server 22a550a) — bereits auf Zielbranch
- scripts/branding_pilot_ui_visual.py
- docs/platform-unification/evidence/ui-visual/**

## Fremd / unberührt
- CRM Dirty: ~263 Pfade, ~99 Dialer-/Softphone-/PSTN-/Allowlist-ähnlich
- CRM UI-Overlap mit Dirty: **keine**
- Server Dirty: umfangreiches Agency-/Dialer-/Ops-WIP — **nicht stagen**
- Production: kein Deploy

## Dialer / PSTN / Allowlist / WebRTC / AMI / Placetel
Integration berührt diese Pfade **nicht**.
