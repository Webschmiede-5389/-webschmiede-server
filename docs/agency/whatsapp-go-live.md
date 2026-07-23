# WhatsApp Go-Live: Nils unterwegs (Meta Cloud API)

Stand: 2026-07-19  
Ziel: Du schreibst von **privat** an die **Business-Nummer** → Nils antwortet.

## Live-Status prüfen

```bash
python scripts/check_messaging_status.py
```

API (Agency-Passwort): `GET /api/nils/whatsapp-ops`

| Braucht | Stand typisch |
|---------|----------------|
| Webhook Verify | oft schon ok |
| `WHATSAPP_ACCESS_TOKEN` | oft **fehlt** |
| `WHATSAPP_PHONE_NUMBER_ID` | oft **fehlt** |
| `OWNER_PHONE` (+49 privat) | setzen |
| `META_APP_SECRET` | empfohlen (Signatur) |

## Deine Klicks (~15 Min)

### 1. Meta Developers

1. https://developers.facebook.com/apps → App mit **WhatsApp**
2. WhatsApp → **API-Setup**
3. Kopieren: **Phone number ID** (lange Zahl, nicht +49)
4. Token: erst Test-Token, besser dauerhaft **System User** mit  
   `whatsapp_business_messaging` + `whatsapp_business_management`

### 2. Webhook

- URL: `https://digitalehandwerkskunst.de/api/whatsapp/webhook`
- Verify-Token: gleiches Geheimnis wie in Agency-Setup (`WHATSAPP_VERIFY_TOKEN`)
- Abonnieren: **messages**

### 3. Bei uns eintragen

https://digitalehandwerkskunst.de/agency-setup → Messaging:

1. `WHATSAPP_ACCESS_TOKEN`
2. `WHATSAPP_PHONE_NUMBER_ID`
3. `OWNER_PHONE` = deine Privatnummer (`+49…`)
4. Optional: `NILS_OPS_OWNER_PHONES` wenn mehrere Handys
5. Optional: `WHATSAPP_DISPLAY_PHONE`, `META_APP_SECRET`
6. Button **WhatsApp (Meta)** testen → grün

### 4. Erster Ping

Vom Handy (privat) an die Business-Nummer:

```
Nils Status
```

Erwartung: Antwort von Nils (Ops scharf / was fehlt).

Dann normal Aufträge, Fotos, Links. Riskante Sachen fragt Nils nach („ja“ zum Bestätigen).

## Nummer-Modell

- Business-Nummer = Meta API = Nils  
- Du = privat → schreibst an Business  
- Fremde an Business = kurze Absage (kein Kunden-Bot)

## Wenn fertig

Schreib mir: **Token drin** oder **WhatsApp-Button grün**.  
Dann prüfen wir den ersten echten Ping.

## Nicht jetzt

- seven.io / Massen-WA / GHL  
- Coexistence Handy+API (optional später)
