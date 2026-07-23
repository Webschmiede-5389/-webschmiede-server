# B2B Kundenportal (Gesicht fuer n8n)

Stand: 2026-07-19

## Entscheidung

**Kein Budibase als Pflicht.** Ihr habt schon Flask/Cursor-Portale.  
Budibase waere ein zweites System (Wartung, Auth, Updates). Optional spaeter evaluieren, nicht jetzt installieren.

Was fehlte und jetzt da ist: Upload → Berechnung → Tabelle → Buchhaltungs-Zaehler auf **eigenen Servern**.  
**Zero-Retention:** Default an, Rohdatei + Zeilen nach 24h weg (Nightly + `/api/b2b/jobs/purge`).

## Live

- UI: https://digitalehandwerkskunst.de/b2b-portal.html (nach Deploy)  
- oder Kunden-Domain Webroot analog  
- API: `/api/b2b/jobs/upload`, `/run`, `/api/b2b/jobs`

Auth: `X-Agency-Password` oder `X-B2B-Token` (= Env `B2B_PORTAL_TOKEN` wenn gesetzt).

## CSV-Format

Spalten ( `;` oder `,` ): `ean`, `name`, `einkauf`, `vk`

MVP-Rechnung ohne Keepa:  
`Marge ≈ VK - EK - 15% VK` (Amazon-Gebuehr-Schaetzung). Keepa erst nach Kosten-OK.

## Optional n8n

`infra/n8n/workflow-b2b-wholesale.json`  
Env `B2B_WHOLESALE_WEBHOOK=https://…/webhook/b2b-wholesale`  
Ohne Webhook rechnet das Backend lokal.

## Budibase (nur Notiz, nicht installiert)

Docker-Compose-Skizze: `infra/docker/budibase.compose.yml`  
Nur nach ausdruecklichem OK von Christian aufsetzen. Stefan-Filter: Vorsicht / Portal zuerst.

## Dateien

| Datei | Zweck |
|-------|--------|
| `app/static/b2b-portal.html` | UI |
| `app/backend/b2b_portal.py` | Jobs + CSV |
| `infra/n8n/workflow-b2b-wholesale.json` | optional Hook |
