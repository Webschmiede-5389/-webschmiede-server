"""Stripe Checkout + Webhook für Agency-Kunden (Setup + Abo)."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import stripe

from agency_packages import AGENCY_LEGAL, PACKAGES

KUNDEN_DIR = Path(os.getenv("KUNDEN_DIR", Path(__file__).resolve().parents[1] / "kunden"))
DEPLOY_SECRETS = Path(os.getenv("DEPLOY_SECRETS_PATH", "/root/app/deploy.secrets.local"))
if not DEPLOY_SECRETS.exists():
    DEPLOY_SECRETS = Path(__file__).resolve().parents[2] / "deploy.secrets.local"


def _read_secrets_file() -> dict[str, str]:
    out: dict[str, str] = {}
    if not DEPLOY_SECRETS.exists():
        return out
    for line in DEPLOY_SECRETS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def stripe_configured() -> bool:
    return bool(_stripe_secret())


def _stripe_secret() -> str:
    return os.getenv("STRIPE_SECRET_KEY", "") or _read_secrets_file().get("STRIPE_SECRET_KEY", "")


def _webhook_secret() -> str:
    return os.getenv("STRIPE_WEBHOOK_SECRET", "") or _read_secrets_file().get("STRIPE_WEBHOOK_SECRET", "")


def _configure_stripe():
    key = _stripe_secret()
    if not key:
        raise RuntimeError("STRIPE_SECRET_KEY fehlt (deploy.secrets.local)")
    stripe.api_key = key


def load_kunde(kid: str) -> tuple[dict, Path] | None:
    kid = kid.upper()
    if not KUNDEN_DIR.is_dir():
        return None
    for p in KUNDEN_DIR.glob("*.json"):
        if p.name.startswith(kid):
            return json.loads(p.read_text(encoding="utf-8")), p
    return None


def save_kunde(k: dict, path: Path):
    path.write_text(json.dumps(k, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def list_packages() -> list[dict]:
    return [{k: v for k, v in pkg.items() if not k.endswith("_cents")} for pkg in PACKAGES.values()]


def create_checkout_session(
    *,
    kunde_id: str,
    package_id: str,
    customer_email: str | None = None,
    success_url: str | None = None,
    cancel_url: str | None = None,
) -> dict:
    _configure_stripe()
    pkg = PACKAGES.get(package_id)
    if not pkg:
        raise ValueError(f"Unbekanntes Paket: {package_id}")

    loaded = load_kunde(kunde_id)
    if not loaded:
        raise ValueError(f"Kunde {kunde_id} nicht gefunden")
    kunde, _ = loaded

    base = (
        kunde.get("urls", {}).get("test_hauptseite")
        or kunde.get("urls", {}).get("live_hauptseite")
        or "https://digitalehandwerkskunst.de"
    ).rstrip("/")

    email = customer_email or kunde.get("kontakt", {}).get("email")
    if not email:
        raise ValueError("Keine E-Mail beim Kunden. customer_email angeben")

    onboarding = kunde.get("urls", {}).get("onboarding_url") or f"{base}/onboarding?k={kunde_id}"
    ok_url = success_url or f"{onboarding}&paid=1"
    cancel = cancel_url or onboarding

    session = stripe.checkout.Session.create(
        mode="subscription",
        customer_email=email,
        client_reference_id=kunde_id,
        metadata={
            "kunde_id": kunde_id,
            "package_id": package_id,
            "shop_name": kunde.get("name", ""),
        },
        subscription_data={
            "metadata": {"kunde_id": kunde_id, "package_id": package_id},
        },
        line_items=[
            {
                "price_data": {
                    "currency": "eur",
                    "unit_amount": pkg["monthly_cents"],
                    "recurring": {"interval": "month"},
                    "product_data": {
                        "name": f"Webschmiede Wartung · {pkg['name']}",
                        "description": f"Hosting, Updates, Support ({pkg['monthly_eur']} €/Monat)",
                    },
                },
                "quantity": 1,
            },
            {
                "price_data": {
                    "currency": "eur",
                    "unit_amount": pkg["setup_cents"],
                    "product_data": {
                        "name": f"Einrichtung · {pkg['name']}",
                        "description": pkg["description"],
                    },
                },
                "quantity": 1,
            },
        ],
        success_url=ok_url,
        cancel_url=cancel,
        billing_address_collection="required",
        tax_id_collection={"enabled": True},
        invoice_creation={"enabled": True},
        payment_method_collection="always",
        allow_promotion_codes=True,
    )

    return {
        "session_id": session.id,
        "url": session.url,
        "kunde_id": kunde_id,
        "package": package_id,
        "email": email,
    }


def handle_webhook(payload: bytes, sig_header: str) -> dict:
    _configure_stripe()
    secret = _webhook_secret()
    if not secret:
        raise RuntimeError("STRIPE_WEBHOOK_SECRET fehlt")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, secret)
    except stripe.error.SignatureVerificationError as e:
        raise ValueError("Ungültige Stripe-Signatur") from e

    etype = event["type"]
    if etype == "checkout.session.completed":
        from provision import provision_after_payment

        session = event["data"]["object"]
        return provision_after_payment(session)

    return {"ok": True, "ignored": etype}


def next_invoice_number(kunde_id: str) -> str:
    year = datetime.now(timezone.utc).year
    return f"WS-{year}-{kunde_id}"


def render_invoice_html(
    *,
    kunde: dict,
    package: dict,
    invoice_no: str,
    paid_at: str,
    stripe_session_id: str,
) -> str:
    inhaber = kunde.get("inhaber", "")
    name = kunde.get("name", "")
    addr = kunde.get("kontakt", {}).get("adresse", "")
    setup = package["setup_eur"]
    monthly = package["monthly_eur"]
    total = setup + monthly

    return f"""
<table style="width:100%;font-family:Arial,sans-serif;font-size:13px;color:#333;border-collapse:collapse;margin:16px 0">
  <tr><td colspan="2" style="padding-bottom:12px;border-bottom:2px solid #C9A84C">
    <strong style="font-size:16px">{AGENCY_LEGAL['name']}</strong><br>
    <span style="color:#666">Rechnung {invoice_no} · {paid_at[:10]}</span>
  </td></tr>
  <tr><td style="padding:12px 0;vertical-align:top;width:50%">
    <span style="color:#888;font-size:11px">RECHNUNGSADRESSE</span><br>
    <strong>{inhaber}</strong><br>{name}<br>{addr}
  </td><td style="text-align:right;color:#666;font-size:12px">
    Stripe-Zahlung bestätigt<br>Ref: {stripe_session_id[:24]}…
  </td></tr>
</table>
<table style="width:100%;border-collapse:collapse;font-size:13px">
  <tr style="background:#1a1712;color:#e8c76a">
    <th style="padding:8px;text-align:left">Leistung</th>
    <th style="padding:8px;text-align:right">Betrag</th>
  </tr>
  <tr><td style="padding:8px;border-bottom:1px solid #eee">Einrichtung {package['name']}</td>
      <td style="padding:8px;border-bottom:1px solid #eee;text-align:right">{setup:.2f} €</td></tr>
  <tr><td style="padding:8px;border-bottom:1px solid #eee">1. Monat Wartung & Hosting</td>
      <td style="padding:8px;border-bottom:1px solid #eee;text-align:right">{monthly:.2f} €</td></tr>
  <tr><td style="padding:8px;font-weight:bold">Gesamt (erste Zahlung)</td>
      <td style="padding:8px;font-weight:bold;text-align:right;color:#C9A84C">{total:.2f} €</td></tr>
</table>
<p style="font-size:11px;color:#888;line-height:1.5">{AGENCY_LEGAL['vat_note']}<br>
Ab dem 2. Monat: {monthly:.2f} €/Monat (Stripe-Abo, kündbar gemäß Vertrag).</p>
"""
