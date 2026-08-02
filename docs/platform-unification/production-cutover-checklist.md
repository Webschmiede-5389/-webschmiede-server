# Production Cutover Checklist

**PRODUCTION_CUTOVER_READY erfordert separate Freigabe von Christian.**

Dieser Auftrag setzt **keinen** Cutover um.

## Vor Cutover

- [ ] Staging Abnahme grün  
- [ ] Visuelle Evidence abgelegt  
- [ ] CRM funktionaler Smoke (ohne Kundenmails)  
- [ ] Tool-Registry Allowlist final  
- [ ] Backup / Tag gesetzt  
- [ ] Rollback-Befehl dokumentiert und getestet (Staging)  
- [ ] Shipcheck für alle kommunizierten Live-Links  
- [ ] Tenant-Isolation bestätigt  

## Cutover-Reihenfolge (Vorschlag)

1. Shared CSS / Assets auf Static CDN-Pfad  
2. CRM Shell (hinter Feature-Flag oder kurzes Deploy-Fenster)  
3. Cockpit Werkzeuge-Tab  
4. Preview Studio / Lead Creator  
5. Agency Hub auf Registry umbiegen  

## Rollback Production

```text
# CRM: vorheriges Release-Tag / Compose Image
# Static Cockpit: git checkout <tag> -- app/static/agency.html && deploy (nur nach OK)
# Nie: DB-Migration rückgängig „blind“; Branding-Cutover sollte schemalos sein
```

## Nach Cutover

- [ ] Healthchecks  
- [ ] Screenshot-Stichprobe  
- [ ] Christian einmal laut „sieht aus wie ein Produkt?“  

## Verboten ohne Freigabe

- `python deploy.py` Production im Rahmen Unification  
- agency-web Publish  
- DNS/Proxy-Änderungen  
- Geschäftsdaten-Migration
