# Navigation Map

**Stand:** 2026-08-02 · Soll-Zustand nach Unification

## Prinzip

Jede **eigene** interne App bietet mindestens:

| Element | Ziel |
|---------|------|
| Zurück zum Agency Cockpit | `/agency` oder absolute Agency-URL |
| Werkzeuge | Cockpit Tab /tools bzw. `/agency#tools` |
| Profil | app-eigene Settings/Profil-Route |
| EnvironmentBadge | production / staging / local |
| Abmelden | app-eigene Logout-Route |
| Hilfe / Doku | `documentation_url` aus Registry oder `/agency-hub` |
| Mandantenkontext | wenn Multi-Tenant (CRM Tenant-Name) |

**Kein** unkontrolliertes Session-Sharing. SSO nur planen/analysieren.

## Ist-Zustand Cross-Links

| Von | Nach | Heute |
|-----|------|-------|
| Agency Hub | Agency, Nils, Setup, Website, Akquise | hardcoded |
| Cockpit | Setup | Link Fuß |
| Cockpit | Cal.com | Link Übersicht |
| CRM | — | kein Link zum Cockpit |
| Lead Creator | — | kein Link zum Cockpit |
| Preview Studio | bleibt in Cockpit | ok |
| Sales Dashboard | isoliert | Legacy |

## Soll-Graph

```
Agency Cockpit (Hub)
├── Werkzeuge (Registry)
│   ├── CRM ──► (new tab) + Link zurück
│   ├── Lead Creator ──► + Link zurück
│   ├── n8n / Cal / DocuSeal / … (external, noopener)
│   └── Kundenportale (Rollen)
├── Preview Studio (Modul)
├── Jarvis / Inbox / …
└── Setup
```

## CRM Navigation (funktional unverändert)

Dashboard · Unternehmen · Kontakte · Pipeline · Aufgaben · Leitfaden · Einwände · Angebote · Kampagnen · Termine · Import · Vertrieb · Einstellungen  

Plus Fuß/Header: Cockpit · Werkzeuge · Env · Logout

## Login / Auth Seiten Inventur

| Seite | Ort | Branding Ist |
|-------|-----|--------------|
| Agency Admin Login | agency.html `#login-screen` | gut (Referenz) |
| Agency 2FA / Forgot / Reset | gleiche Datei | gut |
| CRM Login | crm `auth/login.html` | „A“-Mark, Anfragen-Text |
| CRM Superadmin (falls separat) | prüfen | — |
| Shop Admin Login | admin.html | Dark Gold (Customer) |
| Kunden Konto | konto.html | Customer |
| Agency Hub Ops | password gate | light |
| DHK Leads | HTTP basic / form | warm orange |
| n8n / Cal / DocuSeal / Retell / Meta | Vendor | EXTERNAL — nicht nachbauen |

## Staging-Hinweis

Staging muss klar als Staging erkennbar sein (Badge), ohne interne Container-Namen (`crm.local`, `prod-admin`) prominent.

## SSO (nur Analyse)

| Option | Status |
|--------|--------|
| Getrennte Sessions Agency vs CRM vs Leads | Ist |
| Shared Cookie Domain `.digitalehandwerkskunst.de` | möglich, Sicherheitsanalyse nötig |
| OIDC | nicht vorhanden |

Empfehlung SCHRITT 1: **kein SSO bauen**. Cross-Links + klare Logins. SSO als eigenes Projekt nach Pilot.
