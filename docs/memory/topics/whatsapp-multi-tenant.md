# Topic: WhatsApp Multi-Tenant (GHL-Ersatz)

Stand: 2026-07-17 · umgesetzt in Flask (nicht Node).

## Architektur

- **Agentur:** `WHATSAPP_*` in `.env` (Digitale Handwerkskunst / Nils)
- **Kunden:** `kunden/*.json` → `whatsapp.phone_number_id`, `waba_id`, `access_token` (Embedded Signup)
- **Webhook:** `POST /api/whatsapp/webhook` · Signatur `X-Hub-Signature-256` wenn `META_APP_SECRET` gesetzt
- **Routing:** `metadata.phone_number_id` im Webhook → Tenant → Jarvis-Bot

## API

| Endpoint | Zweck |
|----------|--------|
| `POST /api/whatsapp/send` | Agency-Auth · `kunde_id`, `to`, `template`/`text` |
| `GET /api/onboarding/<kid>/whatsapp/config` | Embedded Signup Config |
| `POST /api/onboarding/<kid>/whatsapp/complete` | OAuth-Code → Token → kunden.json |
| `GET /api/agency/messaging/status` | inkl. `whatsapp_tenants` |

## Agency Setup (neu)

- `META_APP_ID`, `META_APP_SECRET`, optional `META_EMBEDDED_CONFIG_ID`

## Nächster Schritt

- Meta Tech Provider (falls Embedded Signup in Produktion hängt)
- Agentur-Token + Phone Number ID eintragen
- Kunde: Onboarding → WhatsApp verbinden
