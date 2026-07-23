"""Shared HTML layout for agency transactional emails (Orange · Weiß)."""
from __future__ import annotations

ORANGE = "#FF6600"
ORANGE_SOFT = "#FFF4ED"
ORANGE_BORDER = "#FFD4B8"
INK = "#1A1A1A"
MUTED = "#666666"
BG = "#F5F5F5"

SITE_URL = "https://digitalehandwerkskunst.de"
LOGO_URL = f"{SITE_URL}/ci/webschmiede-logo.png"
EMAIL = "info@digitalehandwerkskunst.de"
PHONE_DISPLAY = "0177 8011350"
PHONE_LINK = "tel:+491778011350"


def default_footer_lines(*, reply_email: str | None = None) -> list[str]:
    """Plain-text footer lines."""
    lines = [
        "Christian Kummetat · Webschmiede · Digitale Handwerkskunst",
        PHONE_DISPLAY,
        reply_email or EMAIL,
        "digitalehandwerkskunst.de",
    ]
    return lines


def default_footer_html(*, reply_email: str | None = None) -> str:
    mail = reply_email or EMAIL
    return f"""
    <strong style="color:{INK};">Christian Kummetat</strong><br>
    <span style="color:{MUTED};font-size:11px;">Webschmiede · Digitale Handwerkskunst · Mechernich</span><br><br>
    <a href="{PHONE_LINK}" style="color:{ORANGE};text-decoration:none;">{PHONE_DISPLAY}</a><br>
    <a href="mailto:{mail}" style="color:{ORANGE};text-decoration:none;">{mail}</a><br>
    <a href="{SITE_URL}" style="color:{ORANGE};text-decoration:none;font-weight:600;">digitalehandwerkskunst.de</a>
    """


def email_link(href: str, label: str) -> str:
    return f'<a href="{href}" style="color:{ORANGE};text-decoration:none;font-weight:600;">{label}</a>'


def email_button(href: str, label: str) -> str:
    return (
        f'<a href="{href}" style="display:inline-block;background:{ORANGE};color:#ffffff;'
        f"font-weight:700;padding:14px 28px;border-radius:10px;text-decoration:none;"
        f'font-size:15px;">{label}</a>'
    )


def email_shell(
    *,
    hero_title: str,
    body_html: str,
    hero_subtitle: str = "",
    preheader: str = "",
    footer_lines: list[str] | None = None,
    footer_html: str | None = None,
    reply_email: str | None = None,
) -> str:
    """Responsive table layout · Webschmiede CI (orange/weiß)."""
    pre = (
        f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">'
        f"{preheader}</div>"
        if preheader
        else ""
    )
    sub = (
        f'<p style="margin:10px 0 0;color:{MUTED};font-size:14px;line-height:1.4;">{hero_subtitle}</p>'
        if hero_subtitle
        else ""
    )
    if footer_html:
        foot = footer_html
    elif footer_lines:
        foot = "<br>".join(footer_lines)
    else:
        foot = default_footer_html(reply_email=reply_email)

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="Content-Language" content="de">
  <title>{hero_title}</title>
</head>
<body style="margin:0;padding:0;background:{BG};font-family:Inter,Arial,Helvetica,sans-serif;-webkit-text-size-adjust:100%;">
{pre}
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG};padding:24px 12px;">
  <tr><td align="center">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border-radius:14px;overflow:hidden;border:1px solid #E8E8E8;box-shadow:0 4px 24px rgba(0,0,0,0.05);">
      <tr><td style="padding:28px 28px 20px;text-align:center;border-bottom:3px solid {ORANGE};">
        <a href="{SITE_URL}" style="text-decoration:none;">
          <img src="{LOGO_URL}" alt="Webschmiede" width="200" style="display:block;margin:0 auto;height:auto;max-width:200px;border:0;">
        </a>
        <h1 style="margin:16px 0 0;color:{INK};font-size:20px;font-weight:700;line-height:1.35;">{hero_title}</h1>
        {sub}
      </td></tr>
      <tr><td style="padding:28px 28px 20px;color:#444444;font-size:15px;line-height:1.65;">
        {body_html}
      </td></tr>
      <tr><td style="padding:20px 28px 24px;background:#FAFAFA;border-top:1px solid #E8E8E8;font-size:13px;color:{MUTED};line-height:1.7;">
        {foot}
      </td></tr>
    </table>
  </td></tr>
</table>
</body>
</html>"""


def smtp_test_email(*, reply_email: str) -> tuple[str, str, str]:
    """Subject, plain text, HTML for SMTP connectivity test."""
    subject = "Ihre Webschmiede-E-Mail ist eingerichtet"
    text = f"""Guten Tag,

Ihre E-Mail-Konfiguration für Webschmiede funktioniert.

Diese Nachricht bestätigt, dass automatische Kunden-Mails versendet werden können.

Bei Fragen antworten Sie einfach auf diese E-Mail.

Christian Kummetat · Webschmiede
{PHONE_DISPLAY}
{reply_email}
digitalehandwerkskunst.de
"""
    body = f"""
        <p style="margin:0 0 16px;">Guten Tag,</p>
        <p style="margin:0 0 16px;">Ihre E-Mail-Konfiguration für <strong>Webschmiede</strong> funktioniert einwandfrei.</p>
        <p style="margin:0 0 16px;">Ab sofort können automatische Nachrichten an Ihre Kunden versendet werden.</p>
        <p style="margin:0;color:{MUTED};font-size:13px;">Bei Fragen antworten Sie einfach auf diese Nachricht.</p>
    """
    html = email_shell(
        hero_title="E-Mail-Versand bereit",
        hero_subtitle="Technische Bestätigung",
        preheader="Webschmiede E-Mail ist eingerichtet.",
        body_html=body,
        reply_email=reply_email,
    )
    return subject, text, html
