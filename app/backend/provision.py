"""Nach Stripe-Zahlung: Kunde provisionieren, Passwort, Onboarding-Mail."""
from __future__ import annotations

import json
import os
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agency_mail import send_html_email
from email_templates import email_button, email_shell
from agency_packages import PACKAGES
from stripe_billing import (
    load_kunde,
    next_invoice_number,
    render_invoice_html,
    save_kunde,
)


def _generate_admin_password() -> str:
    return secrets.token_urlsafe(10)


def _set_server_admin_password(password: str):
    """Admin-Passwort auf dem Server (.env) setzen."""
    try:
        import paramiko
        from agency_config import ssh_connect

        env_path = "/root/app/backend/.env"
        safe = password.replace("'", "'\"'\"'")
        client = paramiko.SSHClient()
        ssh_connect(client)
        client.exec_command(
            f"grep -q '^ADMIN_PASSWORD=' {env_path} && "
            f"sed -i 's|^ADMIN_PASSWORD=.*|ADMIN_PASSWORD={safe}|' {env_path} || "
            f"echo 'ADMIN_PASSWORD={safe}' >> {env_path}"
        )
        client.exec_command("systemctl restart snack-api")
        client.close()
        return True
    except Exception:
        return False


def _send_paid_onboarding_email(
    k: dict,
    *,
    admin_password: str,
    package: dict,
    invoice_html: str,
    invoice_no: str,
) -> None:
    name = k.get("inhaber") or k.get("name", "")
    shop = k["name"]
    urls = k.get("urls", {})
    base = (urls.get("test_hauptseite") or "").rstrip("/")
    onboarding = urls.get("onboarding_url") or f"{base}/onboarding?k={k.get('id')}"
    to = k.get("kontakt", {}).get("email")
    if not to:
        return

    subject = f"Zahlung erhalten: {shop} ist freigeschaltet · Webschmiede"

    text = f"""Hallo {name},

vielen Dank für Ihre Zahlung! Ihr System für {shop} ist jetzt freigeschaltet.

Onboarding-Portal: {onboarding}
Admin: {urls.get('test_admin') or base + '/admin'}
Admin-Passwort: {admin_password}
(Bitte beim ersten Login ändern oder sicher aufbewahren.)

Rechnung {invoice_no}, siehe E-Mail HTML.

Webschmiede · Digitale Handwerkskunft
"""

    body = f"""
    <p>Hallo {name},</p>
    <p>vielen Dank für Ihre Zahlung. Ihr Portal für <strong>{shop}</strong> ist jetzt <strong>freigeschaltet</strong>.</p>
    <p style="text-align:center;margin:24px 0;">
      {email_button(onboarding, "Onboarding-Portal öffnen")}
    </p>
    <div style="background:#faf9f7;border:1px solid #eeeeee;border-radius:10px;padding:16px;margin:16px 0;">
      <p style="margin:0 0 8px;font-size:13px;color:#888888;">Admin-Zugang</p>
      <p style="margin:0;font-size:14px;line-height:1.6;"><strong>URL:</strong> {urls.get('test_admin') or base + '/admin'}<br>
      <strong>Passwort:</strong> <code style="background:#eeeeee;padding:2px 8px;border-radius:4px;">{admin_password}</code></p>
      <p style="margin:8px 0 0;font-size:11px;color:#999999;">Bitte sicher aufbewahren.</p>
    </div>
    {invoice_html}
    """

    html = email_shell(
        hero_title="Zahlung erhalten",
        hero_subtitle=f"{shop} · {package['name']}",
        preheader=f"Ihr System für {shop} ist freigeschaltet. Onboarding starten.",
        body_html=body,
        footer_lines=None,
    )

    send_html_email(to=to, subject=subject, html=html, text=text)


def provision_after_payment(session: dict) -> dict:
    """Stripe checkout.session.completed → Kunde live schalten."""
    meta = session.get("metadata") or {}
    kunde_id = (meta.get("kunde_id") or session.get("client_reference_id") or "").upper()
    package_id = meta.get("package_id", "pro")
    session_id = session.get("id", "")

    if not kunde_id:
        return {"ok": False, "error": "kunde_id fehlt in metadata"}

    loaded = load_kunde(kunde_id)
    if not loaded:
        return {"ok": False, "error": f"Kunde {kunde_id} nicht gefunden"}

    kunde, path = loaded
    billing = kunde.setdefault("billing", {})

    if billing.get("stripe_session_id") == session_id:
        return {"ok": True, "duplicate": True, "kunde_id": kunde_id}

    pkg = PACKAGES.get(package_id, PACKAGES["pro"])
    paid_at = datetime.now(timezone.utc).isoformat()
    invoice_no = next_invoice_number(kunde_id)
    admin_pw = _generate_admin_password()

    billing.update({
        "package": package_id,
        "stripe_session_id": session_id,
        "stripe_customer_id": session.get("customer"),
        "stripe_subscription_id": session.get("subscription"),
        "invoice_number": invoice_no,
        "paid_at": paid_at,
        "setup_eur": pkg["setup_eur"],
        "monthly_eur": pkg["monthly_eur"],
    })
    kunde["stripe"] = {
        "status": "aktiv",
        "payment_link": "",
        "subscription_id": session.get("subscription"),
    }
    kunde["status"] = "live"
    save_kunde(kunde, path)

    pwd_ok = _set_server_admin_password(admin_pw)
    invoice_html = render_invoice_html(
        kunde=kunde,
        package=pkg,
        invoice_no=invoice_no,
        paid_at=paid_at,
        stripe_session_id=session_id,
    )

    mail_ok = False
    mail_err = ""
    try:
        _send_paid_onboarding_email(
            kunde,
            admin_password=admin_pw,
            package=pkg,
            invoice_html=invoice_html,
            invoice_no=invoice_no,
        )
        mail_ok = True
    except Exception as e:
        mail_err = str(e)[:200]

    return {
        "ok": True,
        "kunde_id": kunde_id,
        "package": package_id,
        "invoice_number": invoice_no,
        "admin_password_set": pwd_ok,
        "email_sent": mail_ok,
        "email_error": mail_err,
    }
