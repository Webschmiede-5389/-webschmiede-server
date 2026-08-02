# New Project Guidelines

Neue **interne** Anwendungen starten standardmäßig mit Agency Design System.

## Pflicht

- [ ] WebSchmiede-Logo (`/ci/webschmiede-logo-mark.png` oder Wortmarke)  
- [ ] Unterzeile Digitale Handwerkskunst  
- [ ] Design Tokens aus `webschmiede-app.css` / Tailwind Preset (nach SCHRITT 2)  
- [ ] AppShell + Navigation  
- [ ] Login-Layout (LoginCard)  
- [ ] Fehler- / Empty- / Loading-States  
- [ ] Responsive Grundstruktur  
- [ ] EnvironmentBadge  
- [ ] Eintrag in Tool-Registry  
- [ ] Keine hardcodierten Farben außerhalb Tokens  
- [ ] Keine duplizierten Logo-Dateien  

## Stack-Wahl

| Bedarf | Stack |
|--------|-------|
| Internes CRUD / HTMX | FastAPI/Flask + Jinja wie CRM |
| Marketing | agency-web React |
| Kleines Tool | Static HTML + shared CSS |
| Automation UI | Vendor + ToolCard |

## Kundenportale

Branding nur über Tenant-Config ([customer-branding.md](./customer-branding.md)).

## Lint / Review

Vor Merge prüfen:

1. Kein `#C9A84C` in AGENCY_INTERNAL Shells  
2. Kein generisches „W“-Logo wenn CI verfügbar  
3. `rel="noopener noreferrer"` bei external  
4. Shipcheck vor Live-Links an Christian  

## Vorlage (nach SCHRITT 2)

Geplant:

```
templates/agency-app-starter/
  index.html
  login.html
  styles → link webschmiede-app.css
```
