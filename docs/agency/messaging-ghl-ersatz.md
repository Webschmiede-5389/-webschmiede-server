# Messaging-Basis statt GHL

Stand: Juli 2026  
Produktname intern: **Webschmiede Messaging** (CRM + SMS + WhatsApp). Kein GoHighLevel.

**Go-Live jetzt:** [`docs/agency/whatsapp-go-live.md`](whatsapp-go-live.md) · Status: `python scripts/check_messaging_status.py`

## Stack

| Kanal | Anbieter | Wofür |
|-------|----------|--------|
| CRM | Eigenes `contacts` + `message_log` | Kunden, Tags, Verlauf |
| SMS | **seven.io** | Bestell-Links, Reminder, Fallback |
| WhatsApp | **Meta Cloud API** | Bot, Support, Templates |
| Automation | n8n + Cron | Follow-ups |

## Warum Meta + seven, nicht GHL

- GHL = teuer, US, Blackbox  
- seven.io = DE-SMS, API klar, schon im Portal  
- Meta WhatsApp = offizielle Business-API, Nummern über Meta / BSP  
- Alles in unserem Flask + Agency-Setup steuerbar  

## Nummern

1. **SMS-Absender** (`SMS_SENDER`): Name oder freigeschaltete Nummer bei seven  
2. **WhatsApp Business-Nummer**: in Meta Business Suite anbinden (eigene SIM oder Meta-Testnummer)  
3. **Phone Number ID**: Meta-interne ID (nicht die +49-Anzeige) → `WHATSAPP_PHONE_NUMBER_ID`  
4. **Display**: `WHATSAPP_DISPLAY_PHONE` = was der Kunde sieht  

Direkte WhatsApp-Nummern = normale Handynummern im internationalen Format (`+49…`), die der Kunde nutzt. Business-Seite braucht die Meta-Anbindung.

## Zwei getrennte Verbindungen

| Was | Anbieter | Braucht Meta? |
|-----|----------|---------------|
| WhatsApp | **Meta Developers** (Cloud API) | Ja, eigene App |
| SMS | **seven.io** | Nein, komplett getrennt |

GHL mischt das. Wir nicht: erst Meta für WhatsApp, seven.io erst wenn SMS dran ist.

## Meta WhatsApp zuerst (API-Verbindung)

Offiziell: [WhatsApp Cloud API Get Started](https://developers.facebook.com/docs/whatsapp/cloud-api/get-started/)

1. [developers.facebook.com/apps](https://developers.facebook.com/apps) → **Create App** → Use Case **WhatsApp**
2. App an Business Manager / WhatsApp Business Account (WABA) koppeln
3. Links **WhatsApp → API-Setup**:
   - **Phone number ID** notieren (nicht die +49-Anzeige)
   - **WhatsApp Business Account ID** optional notieren
   - Test-Token erzeugen und einmal Testnachricht senden
4. **Webhook** in Meta (Agentur, nicht Kunden-Domain):
   - Callback-URL: `https://digitalehandwerkskunst.de/api/whatsapp/webhook`
   - Verify-Token: gleicher Wert wie `WHATSAPP_VERIFY_TOKEN` bei uns (z. B. `webschmiede-verify`)
   - Feld abonnieren: **messages**  
   Snack House / Kunden-Domains gehören nicht in den Agentur-Webhook.
5. Für Dauerbetrieb: in Business Settings → **System User** → Token mit  
   `whatsapp_business_messaging` + `whatsapp_business_management` (+ ggf. `business_management`)  
   Das ist der **permanente** Token (der temporäre aus dem API-Setup läuft ab).
6. Werte eintragen unter [Agency Setup](https://digitalehandwerkskunst.de/agency-setup) → Messaging:
   - `WHATSAPP_ACCESS_TOKEN`
   - `WHATSAPP_PHONE_NUMBER_ID`
   - `WHATSAPP_VERIFY_TOKEN`
   - optional Display-Nummer / WABA-ID
7. Button **WhatsApp (Meta)** → prüft die Phone Number ID gegen die Graph API

Danach SMS (seven.io) separat. Nicht vorher vermischen.

API-Status: `GET /api/agency/messaging/status`  
Senden: `POST /api/agency/messaging/send` `{ "to": "+49…", "text": "…", "channel": "auto|sms|whatsapp" }`  
Template: `{ "to": "+49…", "channel": "whatsapp", "template": "hello_world" }`

## Regeln (Meta)

- Freitext an Kunden nur im **24h-Fenster** (Kunde hat geschrieben)  
- Außerhalb: **genehmigte Templates** (Bestellbestätigung, Reminder, …)  
- Opt-in beachten (UWG / WhatsApp Policy)  

## Pro Kunde (Paket „Basis statt GHL“)

In `kunden/*.json` schon vorbereitet:

```json
"whatsapp": {
  "enabled": true,
  "phone_number_id": "",
  "allowed_phones": []
}
```

Env pro Server/Kunde: `SMS_*`, `WHATSAPP_*`.  
Code: `app/backend/messaging.py`.

## Checkliste Go-Live Kunde

- [ ] seven.io Guthaben + Absender  
- [ ] Meta WABA + Nummer verifiziert  
- [ ] Webhook grün in Meta  
- [ ] Test-SMS an Inhaber  
- [ ] Test-WhatsApp (erst vom Handy an Business schreiben, dann Antwort)  
- [ ] 1–2 Templates freigegeben (z. B. bestell_link, review_bitte)  
- [ ] Datenschutz: seven.io + Meta genannt  

## Nicht machen

- GHL parallel „nur kurz“  
- Unofficial WhatsApp-Web-Scraping  
- Massen-WA ohne Template/Opt-in  
