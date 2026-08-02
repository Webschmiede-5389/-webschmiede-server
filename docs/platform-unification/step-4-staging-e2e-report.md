# Step 4 — Staging E2E Report

## Was gelaufen ist

1. Isolierte SQLite-DB + TestClient-Smoke (kein Docker-Staging-Stack in diesem Lauf)
2. Login-Branding, Dashboard-Branding, 13 Nav-Routen HTTP 200, `/static/ws/**` Assets 200
3. Evidence: `evidence/step-4/staging-e2e.json`

## Was fehlt für BRANDING_PILOT_READY

- Eigenes Compose/Netzwerk/Ports Staging-Build
- Browser-E2E 1–44 (Playwright) inkl. Agency Werkzeuge
- Viewport-Screenshots 390 / 768 / 1440
- Vollständiger a11y-/Performance-Lauf

**Production:** nicht berührt.
