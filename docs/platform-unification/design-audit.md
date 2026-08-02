# Design Audit — Ist-Werte

**Stand:** 2026-08-02  
**Priorität bei Abweichung:** Agency Cockpit (interne Apps) · öffentliche Website als zweiter Anker · CRM weicht ab

## 1. Agency Cockpit (`agency.html`)

| Token | Wert |
|-------|------|
| Primärorange | `#FF6600` (`--orange`, Tailwind `gold` alias) |
| Hover-Orange | `#E55A00` |
| Orange soft | `#FFF4ED` |
| Orange border soft | `#FFD4B8` |
| Page background | `#F5F5F5` |
| Card / sidebar / header | `#FFFFFF` |
| Text primary | `#1A1A1A` |
| Text muted | `#666666` / `#888` / `#555` nav |
| Border | `#E8E8E8` / inputs `#E0E0E0` |
| Success chip | `#059669` / bg `#ECFDF5` |
| Danger badge | `#e74c3c` |
| Info badge | `#3498db` |
| Font | Inter (Bunny) 400–700 |
| Sidebar width | `15.5rem` (`--sidebar-w`) |
| Topbar height | `3.5rem` |
| Radius panel | `12px` |
| Radius input | `8px` |
| Radius modal | `14px` |
| Shadow card | `0 1px 4px rgba(0,0,0,.04)` |
| Content padding | `1.5rem` |
| Mobile breakpoint sidebar hide | `900px` |
| Pipeline break | `1100px` → 2 Spalten |

### Preview Studio (innerhalb Cockpit) — abweichend

| Token | Wert |
|-------|------|
| Background | `#070605` / `#0e0b08` / `#141210` |
| Accent | `#C9A84C` (Snack-House-Gold) |
| Layout | eigene Dark-Sidebar |

→ **Legacy-Insel** im kanonischen Cockpit.

## 2. Öffentliche Website (`agency-web/tailwind.config.js`)

| Token | Wert |
|-------|------|
| brand.orange | `#FF6600` |
| brand.orange-soft | `#FFF4ED` |
| brand.orange-border | `#FFD4B8` |
| brand.ink | `#1A1A1A` |
| brand.muted | `#666666` |
| brand.bg | `#F5F5F5` |
| brand.border | `#E8E8E8` |
| Font | Inter |
| Button radius | `rounded-xl` |
| Focus ring (CSS) | `#F97316` (leicht abweichend von Primary!) |

**Abweichung Website vs Cockpit:** Focus-Ring `#F97316` vs Border-Focus `#FF6600`. Vorschlag kanonisch: Focus = Primary `#FF6600` mit 20% Ring (wie `.field` in index.css).

## 3. CI Documents (`webschmiede-ci.css`)

| Token | Wert |
|-------|------|
| --ws-orange | `#FF6600` |
| --ws-orange-dark | `#E55A00` |
| --ws-orange-soft | `#FFF4ED` |
| --ws-ink | `#1A1A1A` |
| --ws-ink-muted | `#666666` |
| --ws-border | `#E8E8E8` |
| --ws-problem | `#DC2626` |
| --ws-success | `#16A34A` |
| --ws-radius | `10px` |
| --ws-shadow | `0 4px 24px rgba(0,0,0,0.08)` |

Sehr nah an Cockpit — **beste Seed** für Shared Tokens.

## 4. CRM (`crm/app/static/css/crm.css`)

| Token | Wert | vs Cockpit |
|-------|------|------------|
| --brand | `#FF6600` | gleich |
| --brand-hover | `#E65C00` | ≈ `#E55A00` |
| --brand-soft | `#FFF4ED` | gleich |
| --canvas | `#F7F5F2` | leicht wärmer als `#F5F5F5` |
| --line | `#E8E4DF` | wärmer als `#E8E8E8` |
| --sidebar | `#1A1A1A` | **schwarz — Abweichung** |
| Active nav | volle Orange-Fläche auf Schwarz | Cockpit: soft orange auf Weiß |
| Logo | „W“ CSS | Cockpit: PNG Mark |
| Sidebar width | `240px` | Cockpit `15.5rem` (~248px) |
| Radius | `12px` | ähnlich |
| Font | Inter | gleich |

## 5. Lead Creator (`dashboard/static/style.css`)

| Token | Wert | vs Cockpit |
|-------|------|------------|
| --accent | `#E8600A` | **abweichend** von `#FF6600` |
| Surfaces | `#f7f3ef` / `#ede8e2` | braun-warm |
| Borders | `#e0d8d0` | braun |
| Header | weiß + 2px accent border | kein AppShell |

## 6. Kundenportal SHY001

Dark + Gold `#C9A84C` + Playfair teils — **bewusst anderes Branding** (CUSTOMER_PORTAL). Nicht angleichen an Agency Orange.

## 8. Preflight-Nachweise (2026-08-02)

| URL | Titel | Login | Layout | Farben |
|-----|-------|-------|--------|--------|
| `/agency` | Agency Admin – Webschmiede | ja | Light LoginCard + Shell im DOM | `#FF6600` |
| `crm…/login` | Login · Webschmiede | ja | Light card, **W**-Mark | Orange + Canvas `#F7F5F2` |
| `leads…/` | (leer / Auth-Gate) | vermutl. Basic | — | Template lokal warm `#E8600A` |

Screenshots: `docs/platform-unification/evidence/preflight/`

| Variante | Kennzeichen | Apps |
|----------|-------------|------|
| **A — Agency Light Orange** | Weiß, `#FF6600`, Inter | Cockpit, Hub, CI, agency-web |
| **B — CRM Dark Sidebar** | Schwarze Nav, Orange W | CRM |
| **C — Legacy Brown/Gold** | `#C9A84C`, `#0e0b08` | Preview Studio, Sales Dashboard, Shop |
| **D — Leads Warm Orange** | `#E8600A`, beige Surfaces | Lead Creator |
| **E — Customer Brand** | Tenant Tokens | SHY001 etc. |

## Kanonischer Vorschlag (Entscheidung dokumentiert, nicht still)

Für **AGENCY_INTERNAL**:

- Primär: Cockpit + `webschmiede-ci.css` + BRAND.md  
- Canvas: `#F5F5F5` (nicht CRM `#F7F5F2`)  
- Borders: `#E8E8E8`  
- Hover: `#E55A00`  
- Sidebar: **hell** (CRM umbauen)  
- Focus: `#FF6600`  
- Gold `#C9A84C` nur in CUSTOMER_* Modi oder bewussten Legacy-Inseln bis Migration

Offene Entscheidung für Christian (SCHRITT 2):

1. CRM-Canvas exakt `#F5F5F5` oder leichter Warmton behalten? → **Empfehlung: `#F5F5F5`**  
2. SVG-Logos erzeugen lassen? → erst wenn Originalquelle klar
