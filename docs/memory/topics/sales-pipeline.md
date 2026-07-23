# Topic: Sales-Pipeline

Stand: 2026-07-19

## Beschluss

End-to-End Sales: Christian gibt Mail → Kunde Discovery → automatische Pain-Einschätzung → Preis von Christian → Checkout → Provision.

## Technik

- `app/backend/sales_pipeline.py`
- UI: `sales-dashboard.html`, `sales-angebot.html`
- Hook in `buchhaltung_onboarding.complete`

## Funnel-Begleiter

`sales_companion.py`: Stage-Pings + Reminder-Cron (`setup_sales_companion.py`).

## Freigabe + Wünsche

- Freitext `wuensche` im Discovery
- Kunden-Einschätzung erst nach Christians Freigabe (`awaiting_freigabe_pain`)
- DSGVO: AVV vor Vault, App-Passwörter, keine Klartext-Secrets in API

## Offen / einrichten

SMTP, Stripe, optional WhatsApp + OWNER_PHONE, DocuSeal parallel.
