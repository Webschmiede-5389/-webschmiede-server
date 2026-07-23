# Sales-Pipeline (Webschmiede)

Stand: 2026-07-19

Vom Gespräch bis zur Zahlung, CI-Mails, Discovery-Dashboard, Research, Angebot, Stripe.

## Ablauf

1. **Du** im Sales-Dashboard: E-Mail (+ Firma, optional Telefon/Website) → Einladung  
2. **Kunde** bekommt Mail (CI), öffnet Discovery (`buchhaltung-onboarding.html`)  
3. Tools + Fragen → Empfehlung → AVV → optional Zugänge  
4. Beim Abschluss: **Research** (Website-Signale + Pain-Mapping) → **Einschätzung ohne Preis** per Mail  
5. **Du** setzt Preis im Dashboard → Angebot mit Zahlen per Mail  
6. Kunde klickt „Passt“ → Stripe-Checkout  
7. Nach Zahlung: bestehendes `provision.py` (Zugang + Onboarding-Mail)

Website-Lead: `POST /api/sales/lead` startet dieselbe Kette.

## URLs

- Dashboard (du): `/sales-dashboard.html`  
- Kundeneinschätzung: `/sales-angebot.html?d=DEAL_ID`  
- Discovery: `/buchhaltung-onboarding.html`

## APIs

| Endpoint | Wer |
|----------|-----|
| `POST /api/sales/invite` | Agency |
| `POST /api/sales/lead` | öffentlich |
| `GET /api/sales/deals` | Agency |
| `POST /api/sales/deals/<id>/price` | Agency |
| `POST /api/sales/deals/<id>/checkout` | Agency |
| `POST /api/sales/deals/<id>/accept` | Kunde |
| `GET /api/sales/deals/<id>/public` | Kunde |

## Was du einrichten musst

1. **SMTP** in Agency-Setup (Einladungs-/Angebotsmails)  
2. **Stripe** Keys + Webhook (`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`)  
3. **WhatsApp** optional: Token + Phone ID + `OWNER_PHONE` (Pings an dich)  
4. **DocuSeal** Verträge parallel zum Checkout (noch nicht vollauto im Accept)  
5. Hetzner-AVV / Anwalt vor Großkunden  

## Funnel-Begleiter

Du bekommst bei jedem Schritt eine kurze Meldung (E-Mail, optional WhatsApp):

- Einladung raus · Kunde hat angefangen · Fragen fertig  
- Einschätzung an Kunden → bitte Preis setzen  
- Angebot mit Preis raus · Zahlungslink bereit  
- Erinnerung wenn Formular, Preis, Zahlung oder Vertrag hängen  

Cron alle 4 Stunden: `sales_companion.sh` · Setup `python scripts/setup_sales_companion.py`

## Ehrlichkeit

- Kein Fake-Trustpilot-Scan. Website-Signale + eure Angaben.  
- Telegram/Voice-Outbound: noch nicht.  
- Verträge: DocuSeal manuell/Skript parallel, dann Pay.  
- Nach Pay: Gastro-Onboarding-Pfad; Buchhaltungs-Vault separat exportieren.
