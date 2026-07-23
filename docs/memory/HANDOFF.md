# Handoff (Chat-Neustart)

> Agent füllt das vor einem vorgeschlagenen neuen Chat. Nutzer kopiert den Block unten als erste Nachricht.

```
Lies zuerst:
- docs/memory/CURRENT.md
- docs/memory/HANDOFF.md
- (falls genannt) docs/memory/topics/….md

Ziel:
…

Stand:
…

Nächster Schritt:
…

Nicht anfassen / nicht vermischen:
…

Relevante Dateien:
…
```

## Letzter Handoff

```
Lies zuerst:
- docs/memory/CURRENT.md
- docs/memory/topics/messaging.md
- docs/agency/whatsapp-go-live.md

Ziel:
Meta WhatsApp Cloud API live schalten (GHL-Ersatz). Dann ersten Ping privat → Business.

Stand:
- Verträge/Kundenpaket fertig (DocuSeal).
- WhatsApp-Code + Webhook live und Verify ok.
- WHATSAPP_ACCESS_TOKEN + WHATSAPP_PHONE_NUMBER_ID fehlen noch (nur Christian kann das aus Meta holen).
- n8n-Skizze: infra/n8n/workflow-whatsapp-outbound.json (noch nicht aktivieren).
- Status-Script: python scripts/check_messaging_status.py

Nächster Schritt:
Christian: Meta App → Token + Phone Number ID → Agency Setup → Button „WhatsApp (Meta)“.
Danach: Testnachricht + optional hello_world Template.

Nicht anfassen / nicht vermischen:
Kein GHL. seven.io SMS erst nach WhatsApp-Basis. Keine Käufe ohne OK.

Relevante Dateien:
docs/agency/whatsapp-go-live.md
docs/agency/messaging-ghl-ersatz.md
app/backend/messaging.py
https://digitalehandwerkskunst.de/agency-setup
```
