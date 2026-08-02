# Component Library

**Stand:** 2026-08-02

## CSS-Klassen

Präfix `ws-`. Einstieg: `/ci/webschmiede-app.css` + Root `class="ws-app"`.

| Komponente | Klassen |
|------------|---------|
| BrandLockup | `.ws-brand-lockup` (+ `--full` `--compact` `--icon-only`) |
| AppShell | `.ws-app-shell` `.ws-sidebar` `.ws-main-col` `.ws-topbar` `.ws-main-content` |
| Nav | `.ws-nav-item` `.ws-nav-section` `.is-active` |
| PageHeader | `.ws-page-header` |
| Button | `.ws-btn` `.ws-btn--primary\|secondary\|subtle\|danger\|icon` |
| Forms | `.ws-field` `.ws-input` `.ws-select` `.ws-textarea` `.ws-label` `.ws-switch` |
| Cards | `.ws-card` `.ws-stat-card` `.ws-tool-card` |
| Table | `.ws-table-wrap` `.ws-table` |
| Feedback | `.ws-alert` `.ws-badge` `.ws-empty` `.ws-skeleton` |
| Overlay | `.ws-modal-backdrop` `.ws-modal` |
| Env | `.ws-env-badge` (+ `--local\|staging\|production`) |
| Login | `.ws-login-card` |

## Jinja Macros

`app/backend/templates/shared/ui/macros.html`

- `brand_lockup` · `environment_badge` · `button` · `page_header`
- `alert` · `empty_state` · `tool_card` · `field_input`

Keine Geschäftslogik, keine Tenant-Queries.

## JS

`/ci/webschmiede-ui.js` — Drawer + Modal Escape/Click (minimal).

## Demo

- `/design-system` (APP_ENV=local|staging|test)
- `/design-system/appshell`
