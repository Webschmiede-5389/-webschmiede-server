# Security — Toolübersicht & Cross-Linking

## Pflichtregeln

1. Keine Secrets in Registry, URLs, Query-Parametern  
2. Keine Tokens als `?token=` in Tool-Links  
3. Admin-/Vendor-Links nur für berechtigte Rollen  
4. Staging-URLs nicht in Production-UI für Normalnutzer  
5. Externe Links: `target="_blank"` + `rel="noopener noreferrer"`  
6. Keine unsicheren iFrames von unallowlisteten Hosts  
7. Keine automatische Anmeldung bei Drittanbietern  
8. Kein Cross-Tenant-Zugriff über Tool-Links  
9. Keine offene Redirect-API (`?next=` ohne Allowlist)  
10. URL-Allowlist für `base_url` Hosts  
11. Audit-Log bei Registry-Änderungen (wer/wann)  
12. Manipulierte externe URLs: nur https + Allowlist

## Allowlist-Hosts (Seed)

```
digitalehandwerkskunst.de
crm.digitalehandwerkskunst.de
leads.digitalehandwerkskunst.de
cal.digitalehandwerkskunst.de
sign.digitalehandwerkskunst.de
analytics.digitalehandwerkskunst.de
radar.digitalehandwerkskunst.de
voice.digitalehandwerkskunst.de
snackhouse-yassine.de
```

Vendor (nur ToolCard, Rolle agency_admin):

```
dashboard.retellai.com
web.placetel.de
business.facebook.com
*.google.com (bewusst eng führen)
```

## Tenant Isolation

- Agency Tools ≠ Kundenportal-Admin ohne Rolle  
- SHY001 Admin-Link nur mit Tenant-Kontext  
- Kunden sehen keine Agency n8n/CRM Superadmin

## Auth

- Bestehende Agency-/CRM-Auth beibehalten  
- Kein SSO in diesem Auftrag  
- Login-Seiten ohne interne Hostnamen als Titel

## Was dieser Schritt geprüft hat

- Inventur markiert externe vs interne Systeme  
- Registry-Schema ohne Secret-Felder  
- Explizites Verbot Vendor-UI-Umgestaltung  

Was noch fehlt (SCHRITT 2+): Code-Review der künftigen `/api/agency/tools` Implementierung.
