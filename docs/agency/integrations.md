# Anbindungen (Integrations)

Marketing-Liste: `agency-web/src/data/integrations.ts`  
Sektion: [#integrationen](https://digitalehandwerkskunst.de/#integrationen)  
Logos: `agency-web/public/integrations/` (lokal gehostet)

## Öffentliche Regel

Auf der Website nur zeigen, **was Handwerker kennen** (Lexware, DATEV, Kassen, HubSpot …).

**Nicht öffentlich nennen:** GoHighLevel, n8n und andere Agentur-Werkzeuge. Das gehört hinter die Kulissen.

## Status-Legende

| Status | Bedeutung |
|--------|-----------|
| **Live** | Bei Webschmiede im Einsatz (SMS, Stripe, eigenes CRM, …) |
| **API** | Technisch anbindbar pro Kunde (Lexware, HERO, …) |
| **Export** | DATEV-CSV, Partner-Export |

## Intern (nicht auf der Website)

- Automation-Hub: n8n pro Kunden-ID  
- CRM: eigenes `contacts`, kein GHL  
- Messaging: seven.io SMS + Meta WhatsApp → [`messaging-ghl-ersatz.md`](messaging-ghl-ersatz.md) 

## Pro Kunde (`kunden/*.json`)

```json
"integrations": {
  "buchhaltung": "lexware_office",
  "lexware": {
    "enabled": true,
    "sync_contacts": true,
    "sync_invoices": false,
    "api_key_env": "LEXWARE_API_KEY_SHY001"
  }
}
```

API-Keys **nie** in JSON — nur Env-Variablen auf dem Server (`.env`).

## Lexware Office (Vorlage-Connector)

Siehe `app/backend/integrations/lexware.py` und `scripts/verify_lexware.py`.
