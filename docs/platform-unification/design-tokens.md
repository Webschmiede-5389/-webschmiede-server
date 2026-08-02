# Design Tokens

**Stand:** 2026-08-02 · Datei: `app/static/ci/webschmiede-tokens.css`

## Kernwerte (kanonisch)

| Token | Wert | Herkunft | Verwendung | Abweichung erlaubt? |
|-------|------|----------|------------|---------------------|
| `--ws-brand-primary` | `#FF6600` | BRAND.md / Cockpit | Buttons, Active Nav, Links | nein (Agency) |
| `--ws-brand-primary-hover` | `#E55A00` | CI / Cockpit | Hover | nein |
| `--ws-brand-primary-active` | `#CC5200` | abgeleitet Hover | Pressed | leicht |
| `--ws-brand-primary-soft` | `#FFF4ED` | BRAND | Active bg, chips | nein |
| `--ws-brand-on-primary` | `#FFFFFF` | Kontrast | Text auf Orange | nein |
| `--ws-surface-page` | `#F5F5F5` | Cockpit | Page bg | CRM Warmton später angleichen |
| `--ws-surface-card` | `#FFFFFF` | Cockpit | Karten | nein |
| `--ws-surface-sidebar` | `#FFFFFF` | Cockpit Ziel | Sidebar hell | CRM heute schwarz = Legacy |
| `--ws-text-primary` | `#1A1A1A` | BRAND | Fließtext | nein |
| `--ws-text-muted` | `#666666` | BRAND | Meta | nein |
| `--ws-border-default` | `#E8E8E8` | BRAND | Rahmen | nein |
| `--ws-success` | `#16A34A` | CI | OK | nein |
| `--ws-danger` | `#DC2626` | CI | Fehler | nein |
| `--ws-warning` | `#B45309` | CRM | Warnung | ok |
| `--ws-info` | `#2563EB` | Vorschlag | Info | ok |
| `--ws-font-family` | Inter… | BRAND / Bunny | alles Agency | kein neuer Font |
| `--ws-sidebar-width` | `15.5rem` | Cockpit | Shell | ±0.5rem |
| `--ws-header-height` | `3.5rem` | Cockpit | Topbar | ± |

Vollständige Liste inkl. Spacing/Radius/Shadow: siehe CSS-Datei.

## Legacy-Aliase

`--ws-orange`, `--ws-ink`, `--ws-border` zeigen auf die neuen Namen — für `webschmiede-ci.css` Dokumente.

## Nicht in Tokens

| Farbe | Grund |
|-------|--------|
| `#C9A84C` | Kunden-/Legacy-Gold |
| `#E8600A` | Lead-Creator Übergang |
| CRM Sidebar `#1A1A1A` als Surface | Layout-Entscheidung SCHRITT 3 |
