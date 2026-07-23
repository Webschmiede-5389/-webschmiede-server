# Router-Security (WF1)

Stand: 2026-07-19

## Ziel

Daten von Sekunde eins trennen und nicht unnoetig nach aussen leaken.  
Kein Helsinki-Mythos: Live = **Hetzner Nuernberg**.

## Was live ist

| Kontrolle | Verhalten |
|-----------|-----------|
| Auth | Cron-Secret oder Agency-Passwort Pflicht |
| Rate-Limit | 60/min |
| Tenant | `kunde_id` / `X-Tenant-Id` -> Audit-Trennung |
| PII-Redaktion | E-Mail, Tel, IBAN, secretish in Response/Audit |
| LLM | Nur wenn `AGENCY_ROUTER_LLM=1` **und** keine PII (sonst Regel-Engine) |
| Audit | Tabelle `router_audit`: redigierter Text + Fingerprint, Purge 30 Tage |
| Status | `GET /api/agency/router/security` |

## API

```bash
POST /api/agency/router
{
  "message": "Vertrag fuer Mueller GmbH",
  "kunde_id": "DEMO",
  "redact": true
}
```

Response enthaelt `security`, `tenant_id`, `pii_flags`, `audit_id`.  
Payload/Context sind redigiert (keine Klartext-Mails/Tel in Logs).

## Ehrlichkeit

- Kein „wasserdicht“ / kein „Risiko fast Null“
- Christian kann weiterhin Daten in fremde ChatGPTs kopieren – das blockiert der Router nicht auf dem Laptop
- Was der Router kann: PII nicht an OpenAI schicken, Audit ohne Klartext, Tenant-Trennung in der Agency-API

## Env

```
AGENCY_ROUTER_LLM=0
AGENCY_ROUTER_LLM_ALLOW_PII=0
ROUTER_AUDIT_KEY=langes-geheimnis
```

n8n: `infra/n8n/workflow-agency-router.json` (tenant + redact)
