# Step 3 — Functional Test Report

## Platform Registry

`python -m unittest app.backend.scripts.test_platform_registry -v` → **14 OK**

## Design System (Regression)

`python -m unittest app.backend.scripts.test_design_system -v` → **15 OK**

## CRM

| Suite | Ergebnis |
|-------|----------|
| `tests/test_security_gate.py` | **20 passed** |
| Login HTML smoke | **OK** |
| Full `pytest tests/` | **226 passed**, **4 failed**, **16 errors** |

### Full-Suite Failures (nicht durch Branding verursacht / vorbestehend verdächtig)

- Alembic upgrade/downgrade (`test_014_*`, `test_customer_provisioning` alembic)
- Diverse `test_customer_provisioning` / `test_pol001_graph_recon` Errors (SQLAlchemy/Async)
- `test_handwerk_inquiry_template::test_public_form_http` (403 vs 400)
- `test_placetel_pilot_prep` nonce

**Gate:** Vollständige CRM-Suite ist **nicht** grün → Abnahme `BRANDING_PILOT_READY` blockiert bis Suite bereinigt oder Failures als vorbestehend auf Clean-Branch nachgewiesen.

## Geschäftslogik

Keine Änderungen an Auth-Routen, CSRF-Middleware, RBAC, Lifecycle, Telephony-Services (nur Templates/CSS/Static Sync + Agency Tools API/UI).
