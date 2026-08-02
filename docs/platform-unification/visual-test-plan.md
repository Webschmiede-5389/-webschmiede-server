# Visual Test Plan

**Status:** Baselines für Design-System Lab vorhanden

## Evidence

| Screen | Datei |
|--------|-------|
| Design System Desktop | `evidence/baselines/design-system-desktop.png` |
| AppShell Desktop | `evidence/baselines/appshell-desktop.png` |
| Agency Login Preflight | `evidence/preflight/agency-cockpit-login.png` |
| CRM Login Preflight | `evidence/preflight/crm-login.png` |

Viewports Soll: 390 / 768 / 1440 — Desktop committed; Mobile in SCHRITT 3 mit CRM-Pilot.

Baseline-Updates nur bewusst (kein Auto-Overwrite).

## Referenzscreens je App (Priorität A)

Login · Dashboard · Tabelle · Formular · Detail · Empty · Error · Mobile (~390) · Tablet · Desktop

## Apps in Scope Pilot

1. CRM  
2. Agency Cockpit (Werkzeuge + Dashboard)  
3. (später) Preview Studio, Lead Creator

## Checkliste pro Screen

- [ ] Offizielles Logo vorhanden (kein W-Platzhalter in Agency/CRM Shell)  
- [ ] Keine braunen Altfarben in Shell (`#C9A84C` Shell verboten)  
- [ ] Active Nav korrekt  
- [ ] Buttons / Forms / Tables konsistent  
- [ ] Tabelle nicht abgeschnitten (Scroll-Wrapper)  
- [ ] Kontrast Text/Background OK  
- [ ] Fokus sichtbar  
- [ ] Responsive, kein Horizontal-Overflow der Shell  
- [ ] Keine überlappenden Texte  
- [ ] Sidebar mobil erreichbar  

## Werkzeuge

| Tool | Nutzung |
|------|---------|
| Browser DevTools Mobile | manuell |
| `_preview_server.py` / Preview Studio | vorhandene Preview-Infrastruktur |
| Playwright (falls im Repo) | optional Screenshot-Diff später |
| UX Gate `nils_ux_gate.py` | Heuristik |

## Accessibility (Phase 16 — Plan)

Kontrast · Tastatur · Focus · Labels · ARIA wo nötig · Touch ≥ 44px · Zoom 200% · `prefers-reduced-motion` · verständliche Fehler

## Performance (Phase 17 — Plan)

- Logo PNG Mark ~316 KB → für Favicon/Sidebar skalierte Varianten  
- Favicon 1024px vermeiden in Tabs  
- Font Bunny Inter einmal laden  
- Keine doppelten Tailwind-CDNs unnötig  
- SVG bevorzugen sobald offizielle SVGs vorliegen  

## Visuelle Nachweise (dieser Auftrag)

SCHRITT 1: **keine** neuen Screenshots committed (Analyse only).  
SCHRITT 3/4: Screenshots unter `docs/platform-unification/evidence/` ablegen.
