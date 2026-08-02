# Step 3 — Visual Report (Pilot)

**Stand:** 2026-08-02  
**Methode:** Code-Review + Login-HTML-Smoke (TestClient). Vollständige Screenshot-Baselines **noch nicht** als Artefakte unter `evidence/` abgelegt.

## Geprüft (automatisch / Smoke)

| Screen | Nachweis |
|--------|----------|
| CRM Login | HTML enthält Logo-Mark, „CRM anmelden“, `webschmiede-app.css`, kein „Anfragen-Arbeitsplatz“-Letter |
| CRM AppShell | `base.html` helles Sidebar, BrandLockup, Tenant-Chip, Drawer |
| Agency Werkzeuge | Panel + Nav in `agency.html`; API fail-closed |

## Noch offen für BRANDING_PILOT_READY

- Playwright/Browser-Baselines 390 / 768 / 1440 für alle 9 genannten Screens
- Diff gegen Agency Cockpit (außer Werkzeuge) unverändert
- Automatische Heuristik: kein `#C9A84C`, kein `#E8600A` im CRM-Piloten-CSS (`crm.css` + `ws/ci`) — manuell: Tokens ohne Gold/Leads-Orange

## Update-Parameter Baselines

Nur mit explizitem Flag (noch zu ergänzen): `UPDATE_VISUAL_BASELINES=1`
