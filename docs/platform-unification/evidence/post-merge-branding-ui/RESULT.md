# POST_MERGE_BRANDING_UI_RESULT

**Urteil:** `READY_FOR_LIMITED_PRODUCTION_DEPLOY`

Kein Production-Deploy in diesem Schritt ausgefÃ¼hrt.

## Git

| Feld | Wert |
|------|------|
| Ausgangsbranch (CRM) | `feature/platform-unification-branding-pilot` @ `81398b4` |
| Zielbranch (CRM + Server) | `feature/platform-unification-branding-pilot` |
| Ausgangscommit CRM | `81398b4` |
| Integration CRM | Fast-Forward â†’ `68ede4d` (kein separater Merge-Commit nÃ¶tig, linear) |
| Merge-/Ziel-Commit CRM | `68ede4d` |
| CRM-Commit `68ede4d` enthalten | **ja** |
| Server-Commit `22a550a` enthalten | **ja** (war bereits HEAD) |
| Working Tree sauber (CRM main) | **nein** (Dialer-/Ops-WIP uncommitted, unverÃ¤ndert belassen) |
| Working Tree sauber (CRM verify worktree `crm-postmerge-ro`) | **ja** |
| Working Tree sauber (Server) | **nein** (fremdes Agency-/Ops-WIP; nur Evidence + Visual-Script gestaged) |

## Scope

### Erwartete Dateien (CRM `81398b4..68ede4d`)
- `app/static/css/crm.css`
- `app/templates/companies/archived.html`
- `app/templates/dashboard/index.html`
- `app/templates/leads/list.html`
- `app/templates/tasks/list.html`
- `app/templates/vertrieb/anrufliste.html`
- `tests/test_branding_ui_layout.py`

### Unerwartete Dateien in Integration
- keine

### Dialer/PSTN/Allowlist unverÃ¤ndert
- **ja** (keine dieser Dateien im Scope-Diff; Dirty Dialer-WIP ~99 Pfade unberÃ¼hrt)

### Fremdes WIP unverÃ¤ndert
- **ja** (CRM dirty_total weiterhin ~263; Server-Dirty nicht gestaged auÃŸer Evidence/Script)

## Tests

| Test | Ergebnis | Anzahl |
|------|----------|--------|
| `tests/test_branding_ui_layout.py` | bestanden | 2 |
| `tests/test_handwerk_inquiry_template.py` | bestanden | 9 |
| Branding+Handwerk gesamt | bestanden | **11** |
| `tests/test_security_gate.py` + `tests/test_pipeline_and_score.py` | bestanden | **25** |
| `python -m compileall app` | bestanden | exit 0 |
| Import `from app.main import app` | bestanden | `Webschmiede CRM` |
| Playwright UI visual (5 Viewports) | bestanden | failures 0 |

Dialer-/Softphone-/PSTN-Tests bewusst **nicht** ausgefÃ¼hrt.

## Staging

| Feld | Wert |
|------|------|
| gestartet | **ja** (danach gestoppt) |
| geprÃ¼fter Commit | `68ede4d842b4fdfe67f2d61826ce70a47af25801` |
| URL | `http://127.0.0.1:8093` |
| fÃ¼nf Viewports geprÃ¼ft | **ja** (390Ã—844, 768Ã—1024, 1024Ã—768, 1366Ã—768, 1440Ã—900) |
| Overflow/Overlap | **pass** |
| Console/Netzwerk | **pass** (0 kritische Console, 0Ã— 5xx) |

GeprÃ¼ft u. a.: Login, Shell/Nav, Dashboard, Leads, Tasks, Archiv, Anrufliste, Formulare, Pipeline, Telefonie-Layout (nur visuell).

## Evidence

- `docs/platform-unification/evidence/post-merge-branding-ui/SCOPE.md`
- `docs/platform-unification/evidence/post-merge-branding-ui/git-proof.txt`
- `docs/platform-unification/evidence/post-merge-branding-ui/scope-diff-names.txt`
- `docs/platform-unification/evidence/post-merge-branding-ui/scope-diff-stat.txt`
- `docs/platform-unification/evidence/post-merge-branding-ui/post-check-git.txt`
- `docs/platform-unification/evidence/post-merge-branding-ui/pytest-branding-ui.txt`
- `docs/platform-unification/evidence/post-merge-branding-ui/pytest-crm-smoke.txt`
- `docs/platform-unification/evidence/post-merge-branding-ui/compileall.txt
- Evidence-Commits Server: `ad670b6`, `db3c5bc``
- `docs/platform-unification/evidence/post-merge-branding-ui/import-smoke.txt`
- `docs/platform-unification/evidence/post-merge-branding-ui/staging-start.txt`
- `docs/platform-unification/evidence/post-merge-branding-ui/staging-health.json`
- `docs/platform-unification/evidence/post-merge-branding-ui/staging-commit.txt`
- `docs/platform-unification/evidence/post-merge-branding-ui/visual-run.txt`
- `docs/platform-unification/evidence/post-merge-branding-ui/ui-visual-report.json`
- `docs/platform-unification/evidence/post-merge-branding-ui/screenshots/` (124 Dateien)
- Staging-Log: `projects/crm-postmerge-ro/staging/logs/branding-pilot/uvicorn.log`

## Offene Risiken

1. CRM-Hauptworktree bleibt **dirty** mit Dialer-/Softphone-/PSTN-WIP â€” Deploy darf nur vom **Commit** `68ede4d` (clean tree/checkout), nie aus dem Dirty-Working-Tree.
2. Server-Repo Working Tree ebenfalls dirty (Agency/Ops) â€” Evidence-Commit muss path-selektiv bleiben.
3. GeschÃ¼tzter Stash `wip-before-branding-pilot-step3` war in diesem Snapshot **nicht** in `stash list` â€” Status dokumentieren, nicht neu anlegen.
4. â€žLimited Production Deployâ€œ = nur Branding-UI CSS/Templates; Dialer-Safety und Full-Suite bleiben separater Gate.
5. Kein Production-Deploy in diesem Lauf.


## Evidence-Commits (Server)
- `ad670b6` post-merge evidence + visual runner
- `db3c5bc` compileall marker

