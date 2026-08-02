# CRM AppShell Migration (Pilot)

**Datei:** `projects/crm/app/templates/base.html` + `crm.css` Sidebar-Tokens

## Vorher → Nachher

| Vorher | Nachher |
|--------|---------|
| Sidebar `#1A1A1A` | Hell `#FFFFFF` + Border |
| Buchstaben-Mark „W“ | `logo-mark.png` |
| Tenant als Brand-Unterzeile | Brand fest + Chip „Mandant: …“ |
| Mobile: Sidebar `display:none` | Drawer + Escape + Backdrop |

## Navigation erhalten

Dashboard, Unternehmen, Kontakte, Pipeline, Aufgaben, Leitfaden, Einwände, Angebote, Kampagnen, Termine, Import, Sales-OS/Telefonie (`/vertrieb`), Einstellungen (+ Handwerk-Variante).

## Plattform-Links

Agency Cockpit + Werkzeuge (`target=_blank`, `rel=noopener noreferrer`) — nur Agency-CRM, nicht Handwerk-Inquiry. **Kein SSO.**

## a11y

Skip-Link, `aria-current`, Fokus-Ring, Drawer Escape.
