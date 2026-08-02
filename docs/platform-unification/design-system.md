# Design System (SCHRITT 2 — implementiert)

**Status:** DESIGN_SYSTEM_READY (lokal/Staging-Lab)  
**Einstieg Apps:** `/ci/webschmiede-app.css` + `class="ws-app"`  
**Dokumente/Print:** weiterhin `/ci/webschmiede-ci.css` (importiert Tokens)

## Architektur

```
webschmiede-tokens.css
webschmiede-base.css      # scoped .ws-app
webschmiede-layout.css    # AppShell
webschmiede-components.css
webschmiede-utilities.css
webschmiede-app.css       # @import chain
webschmiede-ui.js         # drawer/modal
```

Keine zweite CI. Keine globalen `button{}`/`table{}` ohne Prefix.

## Lab-Routen

| Route | Gate |
|-------|------|
| `/design-system` | APP_ENV ∈ local, development, staging, test |
| `/design-system/appshell` | gleich |
| Production | **404** |

## Weiter

- Tokens: [design-tokens.md](./design-tokens.md)  
- Components: [component-library.md](./component-library.md)  
- AppShell: [app-shell.md](./app-shell.md)  
- Report: [step-2-report.md](./step-2-report.md)
