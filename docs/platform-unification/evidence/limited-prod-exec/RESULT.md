# LIMITED_BRANDING_UI_PRODUCTION_PASS

**Urteil:** `LIMITED_BRANDING_UI_PRODUCTION_PASS`  
**Rollback erforderlich:** **nein**  
**Zeit (UTC):** 2026-08-04T07:21Z Deploy / 07:22–07:25 Smoke

## Ausgangsimage
- Tag vorher: `crm-app-prod:local`
- Digest: `sha256:640c9e79ea55d037ab9aba191f70f92409b4ded0a01f68e9a87c0e2f3168068d`
- Label `git.sha`: `f0f22780a9a1371ef91298024c84f1bd5aa0ffd6`

## Backup-Tag
- `crm-app-prod:pre-branding-ui-68ede4d` → gleicher Digest `640c9e79…`
- UI-Datei-Backup: `/opt/crm-prod/backups/ui-branding-20260804T072006Z`

## Neues Image
- Tag: `crm-app-prod:branding-ui-68ede4d` (auch als `crm-app-prod:local` für Compose)
- Digest: `sha256:31ada8e913746971d0dbd88fd87e5f788c0c3801a535bfc5b12a14b3fa25d6e1`
- Labels: `branding.ui.commit=68ede4d`, `branding.ui.scope=css+templates-only`, Basis-Label `git.sha=f0f2278…` unverändert geerbt
- Build-Kontext nur: Dockerfile + 7 UI-Dateien (kein Repo-Full-Copy, kein pip)

## Exakt kopierte Dateien (SHA256 = Release `68ede4d`)
1. `app/static/css/crm.css` → `217adbac…`
2. `app/templates/companies/list.html` → `edad9c59…`
3. `app/templates/companies/archived.html` → `43202465…`
4. `app/templates/dashboard/index.html` → `681bc192…`
5. `app/templates/leads/list.html` → `52bc58f6…`
6. `app/templates/tasks/list.html` → `d0ca709f…`
7. `app/templates/vertrieb/anrufliste.html` → `f9e41ead…`

Nachweis Container-Match: `phase2-deploy.json` → `verified[].ok=true`  
Nicht-UI unverändert: `main.py`, `requirements.txt`, `alembic.ini` SHA gleich Backup↔Neu (`phase3b-smoke.json`)

## Container
- Nur `crm-app` recreate (`--no-deps --force-recreate`)
- StartedAt: `2026-08-04T07:21:04.478Z`
- Health: healthy
- Andere Services: `crm-db-prod` unangetastet; Staging-Asterisk/Coturn unverändert

## Health / Login / Alembic
| Check | Vorher | Nachher |
|-------|--------|---------|
| Health | ok, production | ok, production |
| Login | — | **ok** (Redirect `/`) |
| Alembic | `016_dl_meta_context` | `016_dl_meta_context` |

Hinweis: Erster Smoke-Lauf (`phase3`) scheiterte falsch an Selektor `#app-shell` (existiert in Prod-Shell nicht). Login war bereits redirected auf `/`. Korrigierter Lauf `phase3b` grün.

## CSS
- HTTP 200, Länge 15181
- enthält `.table-wrap` und Mobile-Badge-Hide
- SHA256 = Release-CSS

## Smoke je Route (390 + Stichprobe 1440)
| Route | ok | overflowX | Anmerkung |
|-------|----|-----------|-----------|
| Dashboard `/` | ja | nein | wraps=2 |
| Unternehmen | ja | nein | wraps=1 |
| Archiv | ja | nein | |
| Leads | ja | nein | |
| Tasks | ja | nein | |
| Anrufliste | ja | nein | Layout |
| Telefonie | ja | nein | nur Layout, kein Call |
| Pipeline | ja | nein | |
| Console kritisch | 0 | | |
| Network 5xx | 0 | | |

Screenshots: `docs/platform-unification/evidence/limited-prod-exec/screenshots/`

## Dialer / PSTN / Allowlist
- unverändert (kein Config-Touch, keine Calls)
- Health weiterhin `outbound_enabled=false`
- Non-UI Image-Schichten unverändert

## Production-Datenbank
- unverändert (kein Migrate, Alembic 016)

## Rollback
- **nicht erforderlich**
- Bereit: `docker tag crm-app-prod:pre-branding-ui-68ede4d crm-app-prod:local` + compose recreate crm-app

## Quelle
- Release-Checkout: `projects/crm-release-68ede4d` @ `68ede4d` (clean)
- Dirty CRM-Main **nicht** verwendet
