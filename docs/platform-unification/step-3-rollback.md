# Step 3 — Rollback

## webschmiede-server (`feature/platform-unification-branding-pilot`)

```bash
git revert <pilot-commit>
# oder Dateien:
# - config/platform_registry.yaml
# - app/backend/platform_registry.py
# - app/backend/platform_tools.py
# - app/backend/main.py (Tools-Register-Block)
# - app/static/agency.html (Werkzeuge)
# - docs/platform-unification/step-3-* / crm-* / tool-registry / agency-tools / pwa-*
# - scripts/sync_design_system_to_crm.py
# - app/backend/scripts/test_platform_registry.py
```

Stash vor dem Pilot (andere WIP): `git stash list` → `wip-before-branding-pilot-step3`

## CRM (`projects/crm`)

```bash
git checkout -- app/templates/base.html app/templates/auth/login.html app/static/css/crm.css \
  app/static/sw.js app/static/manifest.webmanifest app/jinja_compat.py
rm -rf app/static/ws app/branding.py
```

Kein DB-Migrate nötig (kein Schema-Change).
