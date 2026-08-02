# Step 3 — Staging Report

## Isolierung

| Umgebung | Status |
|----------|--------|
| Production Deploy | **nicht** ausgeführt |
| Production Container | unverändert |
| Production DB | unverändert |
| CRM Staging Docker | in diesem Lauf **nicht** gestartet (Drill unvollständig) |
| Local CRM TestClient | Login-Branding verifiziert |

## Drill-Checkliste (Soll)

1–17 aus Auftrag — **offen** für vollständigen Staging-Container-Lauf.

Lokale Teilschritte erledigt: Asset-Sync, Registry-Filter Prod vs Staging, Design-System Prod-Gate, Login-Smoke.

## Login-Grenzen (Cross-Nav)

CRM ↔ Agency Cockpit: getrennte Sessions, **kein SSO**. Links öffnen neuen Tab; Nutzer meldet sich je System an.
