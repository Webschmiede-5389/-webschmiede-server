# SHY001 Stripe Batch 2 – Test-Mode Checkout Integration

**Datum:** 2026-08-11  
**Worktree:** `webschmiede-server-shy001-baseline-2026-08-11`  
**Branch:** `shy001-prod-baseline-2026-08-11`  
**Deploy:** **NEIN** (nur lokal / Stripe TEST MODE)

```
Scope: KUNDE SHY001
Agency stripe_billing.py: unberührt
online_ordering: bleibt OFF
```

---

## 0. Ist-Zustand (vor Implementierung)

| Thema | Befund |
|-------|--------|
| Agency Stripe | `stripe_billing.py` – Abo/Setup, `mode=subscription`, `/api/stripe/webhook` |
| Shop Checkout | **fehlte** – Frontend hatte Platzhalter `STRIPE_LINK` |
| SDK | `stripe==11.4.0` in `requirements.txt` |
| ENV Agency | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` |
| pay_method | `cash` / `card` / `stripe` |
| Orders-Schema | `pay_method TEXT`, **kein** `payment_status` |
| payment_status Spalte | **nicht vorhanden** → Soft-`ADD COLUMN` nötig (begründet) |

**Schema-Entscheidung:** Ohne Migration kein sauberes PAID/PENDING. Repo-Standard ist Soft-`ALTER TABLE … ADD COLUMN`. Kein destruktives Schema-Rewrite.

**Implementierungsplan:** Eigenes Modul `shop_stripe.py` + Shop-Webhook + Checkout in `create_order` + minimale UI + Tests. Agency-Webhook unverändert.

---

## 1. Architektur

```
Gast wählt Online
  → POST /api/order (pay_method=stripe)
  → Order status=neu, payment_status=pending
  → Checkout Session (mode=payment, EUR, Metadata order_number)
  → Redirect checkoutUrl
  → Stripe zahlt
  → POST /api/shop/stripe/webhook (Signatur!)
  → payment_status=paid
  → order status bleibt neu
  → Mitarbeiter ANNEHMEN (Batch 1)
```

**Regel:** Payment Success ≠ Order Acceptance.

---

## 2. Geänderte / neue Dateien

| Datei | Rolle |
|-------|--------|
| `app/backend/shop_stripe.py` | **NEU** Shop Checkout + Webhook-Logik |
| `app/backend/main.py` | Schema, create_order, Webhooks, Refund-Flag, Labels |
| `app/static/order.html` | Checkout-URL Redirect, Success-Copy |
| `app/static/admin.html` | Zahlungs-Label / Refund-Hinweis |
| `autoprint/autoprint.py` | Bon: ONLINE BEZAHLT vs BARZAHLUNG |
| `kunden/SHY001_snackhouse.json` | `stripe.mode=test`, kein Secret |
| `app/backend/.env.example` | `SHOP_STRIPE_*` dokumentiert |
| `tests/test_shop_stripe.py` | **NEU** |
| `docs/SHY001_STRIPE_BATCH2_2026-08-11.md` | dieses Doc |

---

## 3. Datenmodell

Soft-Migration (`shop_stripe.ensure_schema`):

- `orders.payment_status` TEXT (`unpaid`/`pending`/`paid`/`failed`/`refunded`)
- `orders.stripe_checkout_session_id` TEXT
- `orders.stripe_payment_intent_id` TEXT
- `orders.payment_refund_required` INTEGER DEFAULT 0
- Tabelle `shop_stripe_events` (event_id PK) für Webhook-Idempotenz

Cash: `payment_status=unpaid`  
Stripe vor Zahlung: `pending`  
Nach Webhook: `paid` – **status unverändert**

---

## 4. Checkout Flow

- Endpoint implizit in `POST /api/order` bei `payMethod=stripe`
- Retry: `POST /api/shop/stripe/checkout/<order_number>`
- Betrag: serverseitig `order.total` → Cents (nicht ungeprüft aus Browser neu berechnet über Stripe Line Item)
- Idempotency-Key: `shy001_checkout_{order_number}`
- success_url / cancel_url über `SHOP_PUBLIC_BASE_URL` / `PUBLIC_BASE_URL`
- Success-Text: „Zahlung erfolgreich. Wartet noch auf Bestätigung durch Snack House Yassine.“ – **kein** „angenommen“

---

## 5. Webhook Flow

- **Shop:** `POST /api/shop/stripe/webhook` + `SHOP_STRIPE_WEBHOOK_SECRET`
- **Agency:** `POST /api/stripe/webhook` unverändert
- Events: `checkout.session.completed`, `checkout.session.expired`, `payment_intent.payment_failed`
- Signaturpflicht; Duplikate über `shop_stripe_events`

---

## 6. Payment / Order Trennung

Webhook setzt **nur** `payment_status`.  
Kein Übergang `neu→angenommen` / `neu→zubereitung` durch Stripe.

---

## 7. Barzahlung

Weiterhin `pay_method=cash`, `payment_status=unpaid`, **keine** Checkout Session.

---

## 8. Refund-Fall (PAID + Ablehnen)

Bei `storniert` und `payment_status=paid`:

- `payment_refund_required=1`
- Admin-Hinweis / API-Warning
- **Kein Auto-Refund** in Batch 2 (kontrollierter manueller Stripe-Refund)

---

## 9. Security

- Secret Keys nur Env (`SHOP_STRIPE_SECRET_KEY`, `SHOP_STRIPE_WEBHOOK_SECRET`)
- Nicht in Frontend, Git-Commit-Inhalten als Werte, Tenant-JSON
- Frontend erhält nur `checkoutUrl` (Stripe-hosted)

---

## 10.–11. Tests & Ergebnisse

```
pytest tests/test_shop_stripe.py tests/test_order_acceptance.py
→ 28 passed
```

Abgedeckt u. a.: Cash ohne Session, Checkout Session, Betrag, Paid hält `neu`, Duplikat-Event, ungültige Signatur, Expired/Failed, Refund-Flag, Acceptance-Transitions, Labels.

---

## 12. Bekannte Lücken

- Kein Live-Stripe-E2E in diesem Batch (Keys lokal ggf. nicht gesetzt)
- Kein Auto-Refund
- Autoprint-Agent auf Prod-Pfad ggf. separat syncen beim späteren Deploy
- Soft-Launch OFF → öffentlicher Gast-Checkout noch nicht live testbar ohne Schalter
- Steuer 7/19 % bewusst nicht angefasst (P1)

---

## 13. Deployment-Anforderungen (später, nicht jetzt)

1. `SHOP_STRIPE_SECRET_KEY` (test) + `SHOP_STRIPE_WEBHOOK_SECRET` auf Server  
2. Stripe Dashboard: Webhook → `https://snackhouse-yassine.de/api/shop/stripe/webhook`  
3. Events abonnieren (completed, expired, payment_intent.payment_failed)  
4. `SHOP_PUBLIC_BASE_URL=https://snackhouse-yassine.de`  
5. Minimal-Deploy der Batch-2-Dateien (nicht Full-Repo)  
6. Soft-Launch erst nach Freigabe

---

## STRIPE BATCH 2 RESULT

| Check | Urteil |
|-------|--------|
| Stripe Checkout integration | **PASS** |
| Test mode only | **YES** |
| Payment/order separation | **PASS** |
| Webhook signature verification | **PASS** |
| Webhook idempotency | **PASS** |
| Cash flow preserved | **PASS** |
| Paid-but-rejected handling | **PASS** (Flag, kein Auto-Refund) |
| Acceptance tests | **14 passed / 0 failed** |
| Stripe tests | **14 passed / 0 failed** |
| Unexpected diffs | **NONE** (nur Batch-2 Scope) |
| Ready for Stripe QA Gate | **YES** |
| Ready for production deploy | **NO** |

**STOPP.** Kein Deploy. Soft-Launch bleibt aus.
