# Design System — Spezifikation (SCHRITT 1)

**Status:** Spezifikation only — Shared-Paket noch nicht implementiert (`DESIGN_SYSTEM_READY = nein`)

## Architektur-Entscheidung

| Stack | Empfehlung |
|-------|------------|
| CRM (Jinja/HTMX) | CSS Custom Properties + Komponenten-Partials |
| Agency Static HTML | gemeinsame `webschmiede-app.css` (Erweiterung von `webschmiede-ci.css`) |
| agency-web React | Tailwind Preset aus denselben Tokens (kein zweites Farbsystem) |
| Kundenportale | Tenant-Token-Map, nicht Agency erzwingen |

**Keine** neue SPA-Framework-Einführung nur für Branding.

## Seed (existierend — erweitern, nicht ersetzen)

1. `docs/agency/ci/BRAND.md`  
2. `app/static/ci/webschmiede-ci.css`  
3. Cockpit `:root` in `agency.html`  
4. `agency-web/tailwind.config.js`

Zielpfad (Vorschlag):

```
app/static/ci/webschmiede-app.css          # AppShell Tokens + Utilities
app/static/ci/partials/…                   # optional snipped HTML
# CRM importiert dieselben Token-Werte (Copy oder shared mount /ci/)
```

## Design Tokens (Soll)

| Token | Kanonischer Wert | Quelle |
|-------|------------------|--------|
| brand-primary | `#FF6600` | BRAND / Cockpit |
| brand-primary-hover | `#E55A00` | CI / Cockpit |
| brand-primary-soft | `#FFF4ED` | BRAND |
| brand-primary-border | `#FFD4B8` | Cockpit / Tailwind |
| surface-page | `#F5F5F5` | Cockpit / Website |
| surface-card | `#FFFFFF` | Cockpit |
| surface-sidebar | `#FFFFFF` | Cockpit (CRM Ziel) |
| surface-header | `#FFFFFF` | Cockpit |
| text-primary | `#1A1A1A` | BRAND |
| text-secondary | `#555555` | Cockpit nav |
| text-muted | `#666666` | BRAND |
| border-default | `#E8E8E8` | BRAND |
| status-success | `#16A34A` | CI |
| status-warning | `#B45309` | CRM warn (angleichen) |
| status-danger | `#DC2626` | CI problem |
| status-info | `#2563EB` | Vorschlag (Cockpit `#3498db` nah) |
| focus-ring | `#FF6600` | vereinheitlichen |
| shadow-card | `0 1px 4px rgba(0,0,0,.04)` | Cockpit |
| radius-small | `8px` | inputs |
| radius-medium | `12px` | panels |
| radius-large | `14px` | modals |
| spacing scale | 4/8/12/16/24/32 | 4er-Raster |
| typography | Inter 400/500/600/700 | Bunny |
| sidebar-width | `15.5rem` | Cockpit |
| header-height | `3.5rem` | Cockpit |
| control-height | ~40–44px | Touch |

## Shared Components (Mindestkatalog)

AppShell · BrandHeader · Sidebar · MobileNavigation · PageHeader · Breadcrumbs · Card · StatCard · Button · IconButton · Input · Select · Textarea · Checkbox · Radio · Switch · Badge · Alert · Modal · Drawer · Dropdown · Tabs · Table · Pagination · EmptyState · LoadingState · ErrorState · FormSection · ConfirmDialog · LoginCard · ToolCard · HealthStatus · EnvironmentBadge

### Mapping auf Ist

| Komponente | Cockpit | CRM | CI CSS |
|------------|---------|-----|--------|
| AppShell | `#app` flex | `.app-shell` | — |
| BrandHeader | sidebar brand block | `.brand` (W) | `.ws-brand-lockup` |
| Sidebar | `.sidebar` hell | `.sidebar` dunkel | — |
| Card | `.panel` | cards in css | `.ws-box` |
| Button | `.btn-gold` | `.btn` | `.ws-print-btn` |
| LoginCard | `#login-screen .panel` | `.auth-card` | — |
| ToolCard | Agency Hub `.card` | — | — |

## Kanonisches Layout

### Desktop

- Logo Mark links + WebSchmiede + Unterzeile Digitale Handwerkskunst  
- Helle linke Navigation, Active = orange-soft + orange Text  
- Page bg `#F5F5F5`, Content mit einheitlichem Padding  
- EnvironmentBadge bei Staging  
- Keine abgeschnittene Horizontal-Nav

### Mobil

- Sidebar Drawer oder Bottom Nav (CRM hat bereits `.mobile-bar` — restylen)  
- Header kompakt, Touch ≥ 44px  
- Tabellen horizontal scroll Container  
- Formulare einspaltig

## Branding-Modi

Siehe [customer-branding.md](./customer-branding.md).

## SCHRITT 2 Deliverables (noch offen)

- [ ] `webschmiede-app.css` mit Tokens  
- [ ] Jinja/HTML Partials für AppShell/LoginCard  
- [ ] Tailwind preset Snippet für agency-web  
- [ ] Story-/Beispielseite intern  
- [ ] Visuelle Smoke-Tests lokal
