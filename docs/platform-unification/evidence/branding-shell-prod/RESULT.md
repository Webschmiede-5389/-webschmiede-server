# BRANDING_PRODUCTION_PASS

**Urteil:** `BRANDING_PRODUCTION_PASS`

## Production-URL / Mandant
- URL: https://crm.digitalehandwerkskunst.de/
- Login: https://crm.digitalehandwerkskunst.de/login
- Geprüfter Mandant: **Webschmiede**

## Deploy
- Basis-Image (vor Shell-Deploy): `sha256:31ada8e9…` (`crm-app-prod:branding-ui-68ede4d`)
- Backup-Tag: `crm-app-prod:pre-branding-shell-68ede4d` → gleicher Digest
- Neues Image: `crm-app-prod:branding-shell-68ede4d` → `sha256:2a6ebc828170c403c8d4c693a584f638f1c0ae39ea1e3c051325c488809801de`
- Quelle Templates/Assets: Release-Checkout `68ede4d`
- Zusätzlich zwingend (sonst crashen Templates ohne `ws_brand`):
  - `app/branding.py` (aus `68ede4d`)
  - `app/jinja_compat.py` (aus `68ede4d`)
  - `app/main.py`: **nur** ein Import `import app.jinja_compat` auf Prod-Main (kein Full-`main.py` aus 68ede4d, keine Dialer-Router)
- Alembic unverändert: `016_dl_meta_context`
- Keine Migration, kein Dialer-/PSTN-Touch

## Sichtbare Abnahme (Browser, nicht nur SHA)
| Check | Ergebnis |
|-------|----------|
| Login neues Branding | **ja** (Logo `/static/ws/...`, WebSchmiede) |
| App-Shell `#app-shell` + Sidebar + Topbar | **ja** |
| Dashboard + Unternehmen + Leads | **ja** |
| 390 / 768 / 1440 | **ja**, kein Overflow |
| Assets HTTP 200 | **ja** (`webschmiede-app.css?v=pilot3`, Tokens/Base/Layout/Components, Logo, Favicon, `crm.css?v=pilot3`) |
| Vorher vs Nachher | vorher `hasAppShell=false` → nachher `true` |
| Console kritisch / 5xx | **0** |

## Screenshots
- Vorher: `docs/platform-unification/evidence/branding-shell-prod/screenshots-before/`
- Nachher: `docs/platform-unification/evidence/branding-shell-prod/screenshots-after/`
- Report: `browser-acceptance.json`, `phase2-deploy.json`

## Rollback (falls nötig)
```bash
docker tag crm-app-prod:pre-branding-shell-68ede4d crm-app-prod:local
cd /opt/crm-prod && docker compose -f docker-compose.production.yml --env-file .env.production up -d --no-deps --force-recreate crm-app
```
