# Step 4 — Test Triage

## Umgebung (isoliert)

| Feld | Wert |
|------|------|
| Python | 3.14.4 (`.venv-step4`) |
| Dialect | sqlite (kein CRM_TEST_DATABASE_URL) |
| Runner | `scripts/run_crm_full_test_suite_isolated.ps1` / `.sh` |
| Pilot CRM | `3276689` + Step-4 Fixes |
| Pre-Pilot A/B | worktree `ee1da86` |

## Vorher (System-Python, ohne venv/alembic)

Siehe `evidence/step-4/_failing-subset.txt` und früheren Full-Run: 4 failed / 16 errors.

## Nach Isolation-Fix

`evidence/step-4/full-suite-after-fix.txt`: **246 passed, 0 failed, 0 errors**

## Einzelklassifikation (ursprüngliche 20)

| Test | Klasse | Beleg |
|------|--------|-------|
| test_014_upgrade_downgrade_backfill | TEST_ENVIRONMENT_DEFECT + FIXTURE | alembic nicht installiert / sync URL `sqlite://` bricht async Engine; Fix: venv + `sqlite+aiosqlite://` |
| test_alembic_downgrade_upgrade | TEST_ENVIRONMENT_DEFECT | `No module named alembic.operations` ohne Package; Fix: `.venv-step4` + requirements |
| test_public_form_http (403 vs 400) | FIXTURE_ISOLATION_DEFECT | CSRF_ENABLED=true von security_gate nach Collect; A/B pre-pilot ebenfalls Suite-Pollution |
| test_pilot_guard_nonce… | FIXTURE_ISOLATION_DEFECT | APP_ENV/Flags überschrieben → NOT_STAGING; A/B pre-pilot failed gleichartig in Suite |
| test_customer_provisioning setup Company-ID 8 | FIXTURE_ISOLATION_DEFECT | Geteilte Engine/DB nach Collect; A/B pre-pilot: viele UNIQUE slug Errors |
| test_pol001_graph_recon setup | FIXTURE_ISOLATION_DEFECT | feste slug + shared DB; A/B pre-pilot: IntegrityError tenants.slug |
| test_parallel… POL prefix | FIXTURE_ISOLATION_DEFECT | Default-Prefix `KUN` nach Settings-Reset ohne Modul-Env; Zahlen nicht `POL*` |

**Kein BRANDING_REGRESSION** in den Suite-Failures nachgewiesen (A/B pre-pilot ohne Branding-Commit schlechter/ähnlich pollution).

## Fixes (fachlich sicher)

1. `app/database.py` — `reconfigure_database()`  
2. `tests/conftest.py` — Modul-Autouse: TEST_DB → DATABASE_URL + Rebind  
3. `tests/test_014_…` — async URL für Alembic-Subprocess  
4. Betroffene Module: Rebind + Env-Restore (CSRF, APP_ENV staging, CUSTOMER_NUMBER_PREFIX=POL)  
5. Isolierter Runner + venv mit `requirements.txt` (inkl. alembic)

Auth/Tenant/Lifecycle/Provider-Logik unverändert.
