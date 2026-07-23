#!/usr/bin/env python3
"""Send onboarding welcome email to a client (from Webschmiede agency SMTP)."""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from agency_email import send_html_email

sys.path.insert(0, os.path.join(ROOT, "app", "backend"))
from email_templates import email_button, email_link, email_shell

KUNDEN_DIR = os.path.join(ROOT, "kunden")
DOCS_DIR = os.path.join(ROOT, "docs", "kunden")


def load_kunde(kid: str) -> dict:
    kid = kid.upper()
    for fname in os.listdir(KUNDEN_DIR):
        if fname.endswith(".json") and fname.startswith(kid):
            with open(os.path.join(KUNDEN_DIR, fname), encoding="utf-8") as f:
                return json.load(f)
    raise SystemExit(f"Kunde {kid} nicht gefunden in kunden/")


def handout_path(kid: str) -> str | None:
    p = os.path.join(DOCS_DIR, f"{kid}-uebergabe-handout.html")
    return p if os.path.isfile(p) else None


def build_email(k: dict, *, handout_url: str | None, support_email: str, support_phone: str) -> tuple[str, str, str]:
    name = k.get("inhaber") or k.get("name", "")
    shop = k["name"]
    urls = k.get("urls", {})
    base = urls.get("live_hauptseite") or urls.get("test_hauptseite", "").rstrip("/")
    bestellen = urls.get("live_bestellen") or urls.get("test_bestellen", "")
    admin = urls.get("test_admin") or (f"{base}/admin" if base else "")
    onboarding = urls.get("onboarding_url") or (f"{base}/onboarding?k={k.get('id', '')}" if base else "")

    subject = f"Willkommen bei Webschmiede — Ihr System für {shop} ist bereit"

    text = f"""Hallo {name},

Ihr digitales Bestell- und Verwaltungssystem für {shop} ist eingerichtet.

Ihr Onboarding-Portal (alle Links & Checkliste):
{onboarding}

Ihre Links:
- Website: {base}
- Bestellportal: {bestellen}
- Admin-Dashboard: {admin}

Das Admin-Passwort erhalten Sie separat (nicht per E-Mail).

{f'Handbuch: {handout_url}' if handout_url else ''}

Nächste Schritte:
1. Testbestellung durchführen
2. Admin einmal öffnen und durchklicken
3. Bei Fragen: {support_email or support_phone}

Viele Grüße
Webschmiede · Digitale Handwerkskunft
"""

    html = email_shell(
        hero_title=f"Willkommen, {name}!",
        hero_subtitle=f"Ihr System für {shop} ist bereit.",
        preheader=f"Onboarding für {shop}: Links, Checkliste und nächste Schritte.",
        body_html=f"""
    <p>Sie haben ein <strong>komplettes Paket</strong> erhalten: Website, Online-Bestellportal, Admin-Dashboard und Automatisierungen.</p>
    {f'<p style="text-align:center;margin:20px 0;">{email_button(onboarding, "Onboarding-Portal öffnen")}</p>' if onboarding else ''}
    <table role="presentation" width="100%" style="background:#FAFAFA;border-radius:10px;border:1px solid #E8E8E8;font-size:14px;margin:16px 0;">
      <tr><td style="padding:14px 16px;border-bottom:1px solid #E8E8E8;"><strong>Website</strong><br>{email_link(base, base)}</td></tr>
      <tr><td style="padding:14px 16px;border-bottom:1px solid #E8E8E8;"><strong>Bestellportal</strong><br>{email_link(bestellen, bestellen)}</td></tr>
      <tr><td style="padding:14px 16px;"><strong>Admin-Dashboard</strong><br>{email_link(admin, admin)}<br><span style="font-size:12px;color:#888888;">Passwort erhalten Sie separat (nicht per E-Mail).</span></td></tr>
    </table>
    {f'<p style="text-align:center;">{email_button(handout_url, "Übergabe-Handbuch öffnen")}</p>' if handout_url else ''}
    <h3 style="margin:20px 0 10px;color:#222222;font-size:15px;">Ihre nächsten Schritte</h3>
    <ol style="margin:0;padding-left:20px;color:#555555;font-size:14px;line-height:1.8;">
      <li>Testbestellung durchführen</li>
      <li>Admin öffnen und Bestellung bearbeiten</li>
      <li>Speisekarte prüfen</li>
    </ol>
    """,
    )

    return subject, text, html


def upload_handout(k: dict) -> str | None:
    kid = k["id"]
    local = handout_path(kid)
    if not local:
        return None

    import paramiko
    from agency_config import ssh_connect

    webroot = k.get("server", {}).get("ordner", f"/var/www/{k['slug']}")
    remote_name = "uebergabe-handbuch.html"
    remote_path = f"{webroot}/{remote_name}"

    client = paramiko.SSHClient()
    ssh_connect(client)
    sftp = client.open_sftp()
    sftp.put(local, remote_path)
    sftp.close()
    client.close()

    base = (k.get("urls", {}).get("live_hauptseite") or k.get("urls", {}).get("test_hauptseite", "")).rstrip("/")
    return f"{base}/{remote_name}" if base else None


def main():
    ap = argparse.ArgumentParser(description="Onboarding-E-Mail an Kunden senden")
    ap.add_argument("kunde_id", help="z.B. SHY001")
    ap.add_argument("--dry-run", action="store_true", help="Nur Vorschau, nicht senden")
    ap.add_argument("--upload-handout", action="store_true", help="Handbuch-HTML auf Server hochladen")
    ap.add_argument("--to", help="Override Empfänger-E-Mail")
    ap.add_argument("--support-email", default="", help="Deine Support-E-Mail im Footer")
    ap.add_argument("--support-phone", default="", help="Deine Support-Telefon im Footer")
    args = ap.parse_args()

    k = load_kunde(args.kunde_id)
    to = args.to or k.get("kontakt", {}).get("email")
    if not to:
        raise SystemExit("Keine E-Mail beim Kunden hinterlegt. --to nutzen oder kunden/*.json ergänzen.")

    handout_url = None
    if args.upload_handout:
        print("Lade Handbuch auf Server …")
        handout_url = upload_handout(k)
        if handout_url:
            print(f"Handbuch: {handout_url}")
    elif handout_path(k["id"]):
        base = (k.get("urls", {}).get("test_hauptseite") or "").rstrip("/")
        handout_url = f"{base}/uebergabe-handbuch.html" if base else None

    subject, text, html = build_email(
        k,
        handout_url=handout_url,
        support_email=args.support_email,
        support_phone=args.support_phone,
    )

    if args.dry_run:
        print("=== DRY RUN ===")
        print(f"An:   {to}")
        print(f"Betreff: {subject}")
        print(f"Handbuch-Link: {handout_url or '(nicht gesetzt — --upload-handout)'}")
        print("\n--- Text ---\n")
        print(text)
        return

    send_html_email(to=to, subject=subject, html=html, text=text)
    print(f"Onboarding-E-Mail gesendet an {to}")


if __name__ == "__main__":
    main()
