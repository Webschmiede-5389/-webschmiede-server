# Accessibility (SCHRITT 2 Smoke)

Geprüft am Design-System Showcase / AppShell (synthetisch):

| Check | Ergebnis |
|-------|----------|
| Fokus `:focus-visible` + Focus-Ring Token | ja (CSS) |
| Modal Escape | ja (`webschmiede-ui.js`) |
| Switch `role="switch"` / `aria-checked` | ja |
| Nav `aria-current="page"` | AppShell Demo |
| Labels an Inputs (`field_input` macro) | ja |
| Error `role="alert"` + `aria-describedby` | ja |
| `prefers-reduced-motion` | ja in base.css |
| Kontrast Orange auf Weiß / Weiß auf Orange | Primärfarbe aus BRAND |
| Touch targets mobil ≥44px | mobile-bar / buttons |
| Keine Farbe als einziger Status | Badges + Text |

Offen für SCHRITT 3: voller axe-Lauf auf CRM nach Migration.
