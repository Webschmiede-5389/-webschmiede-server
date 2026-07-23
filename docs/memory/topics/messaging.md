# Topic: Messaging (GHL-Ersatz)

## Stack

- WhatsApp: Meta Cloud API (`WHATSAPP_*`)
- SMS: seven.io (`SMS_*`) – separat, später
- CRM: `contacts` + `message_log`

## Server-Status (2026-07-18)

- Health ok, Webhook-Verify ok
- `WHATSAPP_VERIFY_TOKEN` gesetzt
- Access Token / Phone Number ID: **fehlen** (Christian)
- META_APP_ID / SECRET: fehlen
- SMS API-Key: fehlt (bewusst)
- Check: `python scripts/check_messaging_status.py`
- Go-Live: `docs/agency/whatsapp-go-live.md`

## Setup Meta (Christian)

1. developers.facebook.com/apps → WhatsApp
2. Phone number ID + dauerhafter System-User-Token
3. Webhook: `https://digitalehandwerkskunst.de/api/whatsapp/webhook` + Verify-Token, Feld `messages`
4. Agency Setup speichern → Test „WhatsApp (Meta)“

## Vision

Business-Nummer = Nils (Cloud API). Christian privat schreibt daran.  
Siehe [nils-whatsapp-ops.md](nils-whatsapp-ops.md).

## Doku

- `docs/agency/messaging-ghl-ersatz.md`
- `docs/agency/whatsapp-go-live.md`
