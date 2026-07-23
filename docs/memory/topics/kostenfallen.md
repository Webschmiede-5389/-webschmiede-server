# Kostenfallen-Check

Stand: 2026-07-18

## Sofort erledigt

- Hetzner Capacity-Buyer Cron auf auto-01 **entfernt** (Ziele schon bestellt, `done: true`).  
  War alle 5 Min. aktiv. Kaufte sonst bei Kapazität neue Server (cx43/cx53).

## Grün (kein Auto-Geldloch)

| Thema | Status |
|-------|--------|
| Domain Auto-Kauf | `DOMAIN_AUTO_PURCHASE` aus |
| SMS | `SMS_ENABLED=false` auf Server |
| Stripe | Key lokal leer / Checkout nur Agency |
| Twilio | noch nicht angebunden |
| Jay | 3 Min / 30 Min Tag / Haken / Agency-PW |
| INWX | Account in Prüfung, kein Auto-Kauf |

## Google Places (2026-07-18)

Nacht-Akquise auf auto-01: `places=0`, Log: „kein API-Key“.  
Key liegt lokal/web, nicht im auto-Secrets für den Cron. → **aktuell keine Places-Kosten durch Nachtjobs.**

Rechnung exakt nur in Google Cloud Console (Billing).

3. **Hetzner Fixkosten** – laufende Server (web/auto/…) monatlich. Buyer aus, aber Server laufen weiter.
4. **OPENAI** – lokal leer; wenn du den Key setzt: Nils/Agency-Chat können Tokens fressen (Agency-Login).
5. **Voice-Demo :8090** – nur von web-IP (UFW). Öffentlich über Proxy möglich → CPU, kaum API-€.
6. **Umami/DocuSeal/Cal/n8n** – self-host, praktisch nur Serverstrom.

## Bewusst nicht anfassen ohne OK

- Neue Hetzner-Server
- Twilio-Nummern
- Domain-Käufe
- SMS_ENABLED=true ohne Tageslimit-Check
