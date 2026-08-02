# Staging Rollout

## Umgebungen

| App | Staging-Ansatz |
|-----|----------------|
| CRM | `docker-compose.staging.yml` / Port 8091 / `.env.staging` |
| Agency Cockpit | lokaler snack-api oder Feature-Branch Static — **kein** Live-Deploy ohne Freigabe |
| Lead Creator | lokaler `:5099` oder separates Staging-Host (noch nicht definiert) |
| agency-web | `npm run dev` / preview — Publish gesperrt |

## SCHRITT 4 Abnahme (Staging)

- [ ] Desktop / Tablet / Mobile  
- [ ] RBAC Toolübersicht  
- [ ] Tenant-Isolation Spotcheck  
- [ ] Visuelle Checkliste  
- [ ] Funktionale Regression CRM (Liste öffnen, Deal ansehen — **kein** Live-Mail)  
- [ ] Keine Production-URL versehentlich geändert  

## Rollback Staging

- CRM: vorheriges Image / Git-Tag  
- Static: vorherige Datei aus Git  

Production-Rollback: siehe Cutover-Checkliste (nur nach Freigabe).
