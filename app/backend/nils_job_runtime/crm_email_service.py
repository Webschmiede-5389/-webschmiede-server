# -*- coding: utf-8 -*-
"""Agency CRM e-mail send for Nils — never customer-shop SMTP.

Uses AGENCY_SMTP_* or NILS_SMTP_* only. Recipient must match allowlist.
"""
from __future__ import annotations

import logging
import os
import re
import smtplib
import ssl
from dataclasses import dataclass
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parseaddr
from typing import Any, Callable

log = logging.getLogger("nils_job_runtime.crm_email_service")

_AGENCY_FROM_DOMAINS = frozenset(
    {
        "digitalehandwerkskunst.de",
        "webschmiede.de",
    }
)

# Injected in tests
_SEND_HOOK: Callable[[dict[str, str]], None] | None = None


@dataclass
class SmtpConfig:
    host: str
    port: int
    user: str
    password: str
    from_addr: str
    source: str


def cap_enabled() -> bool:
    raw = (os.getenv("NILS_CAP_CRM_EMAIL") or os.getenv("NILS_CAP_EMAIL_SEND") or "0").strip().lower()
    return raw not in ("0", "false", "no", "off", "")


def dry_run() -> bool:
    raw = (os.getenv("NILS_EMAIL_DRY_RUN") or "0").strip().lower()
    return raw not in ("0", "false", "no", "off", "")


def _env(*names: str) -> str:
    for n in names:
        v = (os.getenv(n) or "").strip()
        if v:
            return v
    return ""


def resolve_agency_smtp() -> SmtpConfig | None:
    """Agency/Nils SMTP only — refuse generic customer SMTP_FROM."""
    host = _env("NILS_SMTP_HOST", "AGENCY_SMTP_HOST")
    user = _env("NILS_SMTP_USER", "AGENCY_SMTP_USER")
    password = _env("NILS_SMTP_PASS", "AGENCY_SMTP_PASS")
    from_addr = _env("NILS_SMTP_FROM", "AGENCY_SMTP_FROM")
    port_raw = _env("NILS_SMTP_PORT", "AGENCY_SMTP_PORT") or "587"
    source = "agency/nils"
    if not host:
        return None
    try:
        port = int(port_raw)
    except ValueError:
        port = 587
    if not from_addr:
        return None
    _, email = parseaddr(from_addr)
    email = (email or from_addr).strip().lower()
    domain = email.rsplit("@", 1)[-1] if "@" in email else ""
    if domain not in _AGENCY_FROM_DOMAINS:
        log.warning("smtp_from_domain_rejected domain=%s", domain)
        return None
    return SmtpConfig(
        host=host,
        port=port,
        user=user,
        password=password,
        from_addr=from_addr,
        source=source,
    )


def allowlist() -> set[str]:
    raw = (
        os.getenv("NILS_EMAIL_ALLOWLIST")
        or os.getenv("AGENCY_OWNER_EMAIL")
        or ""
    )
    parts = re.split(r"[,;\s]+", raw.strip())
    return {p.strip().lower() for p in parts if p.strip()}


def recipient_allowed(to_addr: str) -> bool:
    to = (to_addr or "").strip().lower()
    if not to or "@" not in to:
        return False
    allowed = allowlist()
    if not allowed:
        return False
    if to in allowed:
        return True
    domain = to.rsplit("@", 1)[-1]
    return f"@{domain}" in allowed or domain in allowed


def normalize_email(raw: str) -> str:
    _, email = parseaddr((raw or "").strip())
    return (email or raw or "").strip().lower()


def send_agency_mail(
    *,
    to_addr: str,
    subject: str,
    body_text: str,
    company_name: str = "",
    attachments: list[tuple[str, bytes]] | None = None,
) -> dict[str, Any]:
    """attachments: list of (filename, raw_bytes) — z. B. Angebots-PDF."""
    if not cap_enabled():
        raise PermissionError("NILS_CAP_CRM_EMAIL aus")
    to = normalize_email(to_addr)
    if not recipient_allowed(to):
        raise PermissionError(f"Empfänger nicht auf Allowlist: {to}")
    subj = (subject or "").strip()[:200]
    body = (body_text or "").strip()
    if len(subj) < 2 or len(body) < 2:
        raise ValueError("Betreff oder Inhalt fehlt")
    atts = list(attachments or [])
    att_names = [n for n, _ in atts if n]

    cfg = resolve_agency_smtp()
    payload = {
        "to": to,
        "subject": subj,
        "body": body,
        "company": company_name or "",
        "from": (cfg.from_addr if cfg else ""),
        "dry_run": "1" if dry_run() or not cfg else "0",
        "attachments": ",".join(att_names),
    }
    if _SEND_HOOK is not None:
        _SEND_HOOK(payload)
        return {
            "ok": True,
            "dry_run": True,
            "to": to,
            "subject": subj,
            "message_id": "hook",
            "attachments": att_names,
        }

    if dry_run() or not cfg:
        if not cfg and not dry_run():
            raise RuntimeError(
                "Kein Agency-SMTP (AGENCY_SMTP_*/NILS_SMTP_* mit From @digitalehandwerkskunst.de)."
            )
        log.info(
            "email_dry_run to=%s subject=%s atts=%s",
            to,
            subj[:80],
            att_names,
        )
        return {
            "ok": True,
            "dry_run": True,
            "to": to,
            "subject": subj,
            "message_id": "dry-run",
            "detail": "Dry-Run — keine SMTP-Zustellung",
            "attachments": att_names,
        }

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subj
    msg["From"] = cfg.from_addr
    msg["To"] = to
    if company_name:
        msg["X-Nils-Company"] = company_name[:120]
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(body, "plain", "utf-8"))
    msg.attach(alt)
    for fname, raw_bytes in atts:
        part = MIMEApplication(raw_bytes, _subtype="pdf")
        part.add_header("Content-Disposition", "attachment", filename=fname)
        msg.attach(part)
    _, envelope_from = parseaddr(cfg.from_addr)
    envelope_from = (envelope_from or cfg.from_addr).strip()
    raw = msg.as_string()
    if cfg.port == 465:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(cfg.host, cfg.port, timeout=30, context=context) as s:
            if cfg.user:
                s.login(cfg.user, cfg.password)
            s.sendmail(envelope_from, [to], raw)
    else:
        with smtplib.SMTP(cfg.host, cfg.port, timeout=30) as s:
            s.ehlo()
            s.starttls()
            s.ehlo()
            if cfg.user:
                s.login(cfg.user, cfg.password)
            s.sendmail(envelope_from, [to], raw)
    return {
        "ok": True,
        "dry_run": False,
        "to": to,
        "subject": subj,
        "from": cfg.from_addr,
        "message_id": "smtp-sent",
        "attachments": att_names,
    }


def format_approval(
    *,
    to_addr: str,
    subject: str,
    body: str,
    company_name: str = "",
    offer_number: str = "",
    attachment_name: str = "",
) -> str:
    lines = [
        "Freigabe nötig — Agency-E-Mail senden:",
        f"An: {to_addr}",
    ]
    if company_name:
        lines.append(f"Bezug Firma: {company_name}")
    if offer_number:
        lines.append(f"Angebot: {offer_number}")
    if attachment_name:
        lines.append(f"Anhang: {attachment_name}")
    lines.append(f"Betreff: {subject}")
    lines.append("---")
    preview = (body or "").strip()
    if len(preview) > 600:
        preview = preview[:600] + "…"
    lines.append(preview)
    lines.append("---")
    if dry_run() or resolve_agency_smtp() is None:
        lines.append("(Hinweis: Dry-Run oder Agency-SMTP fehlt — kein echter Versand bis konfiguriert.)")
    lines.append('Antworte mit „ja“ / „freigabe ja“, sonst „stop“.')
    return "\n".join(lines)


def format_sent(result: dict[str, Any]) -> str:
    att = result.get("attachments") or []
    att_line = f"\nAnhang: {', '.join(att)}" if att else ""
    if result.get("dry_run"):
        return (
            "E-Mail Dry-Run OK (nicht zugestellt).\n"
            f"An: {result.get('to')}\n"
            f"Betreff: {result.get('subject') or '—'}"
            f"{att_line}\n"
            f"Beleg: {result.get('message_id')}"
        )
    return (
        "E-Mail gesendet.\n"
        f"An: {result.get('to')}\n"
        f"Von: {result.get('from')}\n"
        f"Betreff: {result.get('subject')}"
        f"{att_line}\n"
        f"Beleg: {result.get('message_id')}"
    )
