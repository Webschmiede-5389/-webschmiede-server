# Branding UI Visual Acceptance

**Urteil:** `BRANDING_UI_STAGING_READY`  
**Basis:** CRM `81398b4` (clean worktree `crm-postmerge-ro`)  
**Branch:** `feature/platform-unification-branding-ui-visual`  
**Staging:** lokal `http://127.0.0.1:8093` — kein Production-Deploy

## Fixes (nur UI-Scope)

- Mobile Topbar: Wrap, Actions volle Breite, STAGING-Badge in Topbar ausgeblendet (`≤900px`)
- `.table-wrap` auf Dashboard, Leads, Tasks, Archiv, Anrufliste
- Scroll-Tabellen: `white-space: nowrap` statt Wort-Zerlegung
- Filter/Toolbar stapeln auf schmalen Viewports

## Checks

- Playwright Viewports: 390×844, 768×1024, 1024×768, 1366×768, 1440×900
- Overflow / Overlap / Shatter-Heuristik: pass (`ui-visual-report.json`)
- Screenshots: `evidence/ui-visual/screenshots/`
- Pytest: `tests/test_branding_ui_layout.py`

## Explizit nicht

- Dialer / Softphone / Allowlist / PSTN / AMI
- Production
- Fremdes Dialer-WIP im Haupt-CRM
