"""Agency SMTP · headers, templates, deliverability."""
from __future__ import annotations

import os
import smtplib
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid, parseaddr
from pathlib import Path

BRAND_NAME = "Webschmiede"


def secrets_path() -> Path:
    env = os.getenv("DEPLOY_SECRETS_PATH", "").strip()
    if env:
        return Path(env)
    server = Path("/root/app/deploy.secrets.local")
    if server.exists():
        return server
    root = Path(__file__).resolve().parents[2]
    return root / "deploy.secrets.local"


def _read_secrets() -> dict[str, str]:
    path = secrets_path()
    values: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            values[key.strip()] = val.strip()
    return values


def load_agency_smtp() -> dict | None:
    values = _read_secrets()
    host = os.environ.get("AGENCY_SMTP_HOST") or values.get("AGENCY_SMTP_HOST")
    user = os.environ.get("AGENCY_SMTP_USER") or values.get("AGENCY_SMTP_USER")
    password = os.environ.get("AGENCY_SMTP_PASS") or values.get("AGENCY_SMTP_PASS")
    if not host or not user or not password:
        return None

    from_raw = os.environ.get("AGENCY_SMTP_FROM") or values.get("AGENCY_SMTP_FROM", "")
    if from_raw.strip():
        from_hdr = from_raw.strip()
    else:
        from_hdr = formataddr((BRAND_NAME, user))

    reply_to = (
        os.environ.get("AGENCY_REPLY_TO")
        or values.get("AGENCY_REPLY_TO", "")
        or user
    ).strip()

    return {
        "host": host,
        "port": int(os.environ.get("AGENCY_SMTP_PORT") or values.get("AGENCY_SMTP_PORT", "587") or "587"),
        "user": user,
        "password": password,
        "from": from_hdr,
        "reply_to": reply_to,
    }


def _domain_from_cfg(cfg: dict) -> str:
    for candidate in (cfg.get("from", ""), cfg.get("user", ""), cfg.get("reply_to", "")):
        _, addr = parseaddr(candidate)
        if "@" in addr:
            return addr.split("@", 1)[1]
    return "digitalehandwerkskunst.de"


def build_message(
    *,
    cfg: dict,
    to: str,
    subject: str,
    html: str,
    text: str | None = None,
    bcc: list[str] | None = None,
) -> MIMEMultipart:
    """Build MIME message with deliverability-friendly headers."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = cfg["from"]
    msg["To"] = to
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=_domain_from_cfg(cfg))
    msg["MIME-Version"] = "1.0"
    msg["Content-Language"] = "de-DE"
    msg["X-Auto-Response-Suppress"] = "All"
    if cfg.get("reply_to"):
        msg["Reply-To"] = cfg["reply_to"]
    if bcc:
        msg["Bcc"] = ", ".join(bcc)

    if text:
        msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    return msg


def _default_bcc() -> list[str]:
    values = _read_secrets()
    raw = (os.environ.get("AGENCY_MAIL_BCC") or values.get("AGENCY_MAIL_BCC", "")).strip()
    if not raw:
        return []
    return [a.strip() for a in raw.split(",") if a.strip()]


def send_html_email(
    *,
    to: str,
    subject: str,
    html: str,
    text: str | None = None,
    bcc: list[str] | None = None,
) -> None:
    cfg = load_agency_smtp()
    if not cfg:
        raise RuntimeError(
            "Agency-SMTP nicht konfiguriert. In deploy.secrets.local eintragen: "
            "AGENCY_SMTP_HOST, AGENCY_SMTP_USER, AGENCY_SMTP_PASS"
        )

    bcc_all = list(dict.fromkeys((bcc or []) + _default_bcc()))
    msg = build_message(cfg=cfg, to=to, subject=subject, html=html, text=text, bcc=bcc_all or None)
    envelope = cfg["user"]
    recipients = [to] + bcc_all

    with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as s:
        s.starttls()
        s.login(cfg["user"], cfg["password"])
        s.sendmail(envelope, recipients, msg.as_string())
