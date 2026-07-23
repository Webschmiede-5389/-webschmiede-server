# Stripe — Agency-Abrechnung (Setup + Abo)

## 1. Stripe Dashboard

1. [dashboard.stripe.com](https://dashboard.stripe.com) → Account für **Webschmiede**
2. **Developers → API keys** → Secret key kopieren (`sk_test_…` zum Testen)
3. In `deploy.secrets.local` (lokal + Server `/root/app/deploy.secrets.local`):

```env
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

Oder unter **http://167.233.211.170/agency-keys** (Gruppe Abrechnung).

## 2. Webhook

**Developers → Webhooks → Add endpoint**

| Feld | Wert |
|------|------|
| URL | `https://digitalehandwerkskunst.de/api/stripe/webhook` |
| Events | `checkout.session.completed` |

Signing secret → `STRIPE_WEBHOOK_SECRET`

## 3. Zahlungslink erstellen

**Agency Admin:** `/agency` → „Kunde abrechnen“

**CLI:**

```bash
python jarvis.py checkout SHY001 pro
python jarvis.py checkout SHY001 starter
```

## Pakete

| ID | Einmalig | Monatlich |
|----|----------|-----------|
| `starter` | 998 € | 298 € |
| `pro` | 1.980 € | 500 € |

## Nach erfolgreicher Zahlung (automatisch)

1. Kunde `status` → `live`
2. Neues **Admin-Passwort** auf Server
3. **Onboarding-E-Mail** mit Rechnung (HTML) + Portal-Link
4. Stripe **Invoice** an Kunden (Stripe-eigen)

## Test

Stripe Testkarte: `4242 4242 4242 4242` · Beliebiges Datum/CVC

```bash
stripe listen --forward-to https://digitalehandwerkskunst.de/api/stripe/webhook
```

(lokal mit Stripe CLI)

## Ablauf Verkauf

```
Demo (muster) → Vorschau-Subdomain → checkout Link → Kunde zahlt → Webhook → Live
```
