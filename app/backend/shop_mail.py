# -*- coding: utf-8 -*-
"""Shop-Kundenmails (SHY001): Logo-Hülle, Consent, Frequency-Cap, Templates, Promo-Blast."""
from __future__ import annotations

import json
import os
import sqlite3
import time
from typing import Any

SHOP_NAME = os.getenv("SHOP_NAME", "Snack House Yassine")
PUBLIC_BASE = (
    os.getenv("ORDER_PORTAL_URL")
    or os.getenv("PUBLIC_BASE_URL")
    or "https://snackhouse-yassine.de"
).rstrip("/")
# Canonical storefront for assets (avoid wrong PUBLIC_BASE_URL on staging)
SHOP_ASSET_BASE = os.getenv("SHOP_ASSET_BASE_URL", "https://snackhouse-yassine.de").rstrip("/")
SHOP_LOGO_URL = os.getenv(
    "SHOP_LOGO_URL",
    f"{SHOP_ASSET_BASE}/img/logo.png",
)

# Marketing templates that require marketing_consent
MARKETING_TEMPLATE_KEYS = frozenset({
    "winback_30d",
    "winback_60d",
    "upsell",
    "promo_blast",
    "welcome_marketing",
    "upsell_drehspiess",
    "upsell_ayran",
    "upsell_loyalty_reminder",
})

TEMPLATE_LABELS: dict[str, str] = {
    "review_request": "Bewertungsanfrage",
    "winback_30d": "Rückholer 30 Tage",
    "winback_60d": "Rückholer 60 Tage",
    "promo_blast": "Aktions-Mail an Kunden",
    "upsell_drehspiess": "Upsell: Drehspieß / Pizza",
    "upsell_ayran": "Upsell: Ayran / Getränk",
    "upsell_loyalty_reminder": "Stempel fast voll",
}


def status_url(order_number: str) -> str:
    """Öffentliche Live-Status-URL für Bestellportal."""
    nr = (order_number or "").strip()
    return f"{SHOP_ASSET_BASE}/bestellen?status={nr}"


def status_cta_html(order_number: str) -> str:
    url = status_url(order_number)
    return (
        f'<div style="text-align:center;margin:24px 0;">'
        f'<a href="{url}" style="display:inline-block;background:linear-gradient(135deg,#C9A84C,#e8c76a);'
        f'color:#000;font-weight:800;font-size:14px;padding:14px 28px;border-radius:10px;text-decoration:none;">'
        f'Live-Status ansehen</a></div>'
        f'<p style="color:#555;font-size:11px;text-align:center;margin:0;">'
        f'Oder Link speichern: <a href="{url}" style="color:#888;">{url}</a></p>'
    )


def plain_to_html(text: str, *, cta_url: str = "", cta_label: str = "") -> str:
    """Klartext (Zeilenumbrüche) → einfaches HTML für Mails."""
    import html as _html
    raw = (text or "").strip()
    if not raw:
        return ""
    parts = []
    for block in raw.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        lines = [_html.escape(ln) for ln in block.split("\n")]
        parts.append(
            '<p style="color:#ccc;font-size:15px;line-height:1.6;margin:0 0 14px;">'
            + "<br>".join(lines)
            + "</p>"
        )
    out = "".join(parts)
    if cta_url and cta_label:
        out += (
            f'<div style="text-align:center;margin:20px 0;">'
            f'<a href="{_html.escape(cta_url)}" style="display:inline-block;'
            f'background:linear-gradient(135deg,#C9A84C,#e8c76a);color:#000;font-weight:800;'
            f'padding:14px 28px;border-radius:10px;text-decoration:none;">{_html.escape(cta_label)}</a></div>'
        )
    return out


def html_to_plain(html: str) -> str:
    """Grobe HTML→Klartext-Konvertierung für den Admin-Editor."""
    import re
    t = html or ""
    t = re.sub(r"(?i)<br\s*/?>", "\n", t)
    t = re.sub(r"(?i)</p\s*>", "\n\n", t)
    t = re.sub(r"(?i)</div\s*>", "\n", t)
    t = re.sub(r"(?i)<h[1-6][^>]*>", "", t)
    t = re.sub(r"(?i)</h[1-6]>", "\n\n", t)
    t = re.sub(r"(?i)<a[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", r"\2 (\1)", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = (
        t.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&nbsp;", " ")
        .replace("&mdash;", "–")
        .replace("&euro;", "€")
    )
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


DEFAULT_TEMPLATES: dict[str, dict[str, str]] = {
    "review_request": {
        "subject": "War alles gut? Kurze Bewertung fuer {{shop_name}}",
        "body_text": (
            "War alles gut, {{name}}?\n\n"
            "Wir hoffen, deine Bestellung hat dir geschmeckt! Eine kurze Bewertung hilft uns enorm.\n\n"
            "Jetzt bewerten: {{review_url}}"
        ),
        "body_html": (
            "<h2 style=\"color:#C9A84C;margin:0 0 16px;font-size:20px;\">War alles gut, {{name}}?</h2>"
            "<p style=\"color:#ccc;font-size:15px;line-height:1.6;\">"
            "Wir hoffen, deine Bestellung hat dir geschmeckt! Eine kurze Bewertung hilft uns enorm.</p>"
            "<div style=\"text-align:center;margin:24px 0;\">"
            "<a href=\"{{review_url}}\" style=\"display:inline-block;background:linear-gradient(135deg,#C9A84C,#e8c76a);"
            "color:#000;font-weight:800;font-size:15px;padding:16px 36px;border-radius:12px;text-decoration:none;\">"
            "Jetzt bewerten</a></div>"
        ),
    },
    "winback_30d": {
        "subject": "Dein Lieblings-Shawarma vermisst dich – {{shop_name}}",
        "body_text": (
            "Lange nicht gesehen, {{name}}!\n\n"
            "Dein Lieblingsessen wartet auf dich.\n\n"
            "Jetzt online bestellen: {{order_url}}"
        ),
        "body_html": (
            "<h2 style=\"color:#C9A84C;margin:0 0 16px;font-size:20px;\">Lange nicht gesehen, {{name}}!</h2>"
            "<p style=\"color:#ccc;font-size:15px;line-height:1.6;\">Dein Lieblingsessen wartet auf dich.</p>"
            "<div style=\"text-align:center;margin:24px 0;\">"
            "<a href=\"{{order_url}}\" style=\"display:inline-block;background:linear-gradient(135deg,#C9A84C,#e8c76a);"
            "color:#000;font-weight:800;padding:14px 32px;border-radius:10px;text-decoration:none;\">"
            "Jetzt online bestellen</a></div>"
        ),
    },
    "winback_60d": {
        "subject": "Letzte Chance: Dein Shawarma wartet – {{shop_name}}",
        "body_text": (
            "Noch da, {{name}}?\n\n"
            "Du warst schon eine Weile nicht mehr bei uns. Sag beim nächsten Mal ICH BIN ZURUECK – wir überraschen dich.\n\n"
            "Jetzt bestellen: {{order_url}}"
        ),
        "body_html": (
            "<h2 style=\"color:#C9A84C;margin:0 0 16px;font-size:20px;\">Noch da, {{name}}?</h2>"
            "<p style=\"color:#ccc;font-size:15px;line-height:1.6;\">"
            "Du warst schon eine Weile nicht mehr bei uns. Sag beim nächsten Mal "
            "<strong style=\"color:#fff;\">ICH BIN ZURUECK</strong> – wir überraschen dich.</p>"
            "<div style=\"text-align:center;margin:24px 0;\">"
            "<a href=\"{{order_url}}\" style=\"display:inline-block;background:linear-gradient(135deg,#C9A84C,#e8c76a);"
            "color:#000;font-weight:800;padding:14px 32px;border-radius:10px;text-decoration:none;\">"
            "Jetzt bestellen</a></div>"
        ),
    },
    "promo_blast": {
        "subject": "Aktion: {{promo_title}} – {{shop_name}}",
        "body_text": (
            "{{promo_title}}\n\n"
            "{{promo_description}}\n\n"
            "Zur Aktion bestellen: {{order_url}}\n\n"
            "Mails abbestellen: {{unsubscribe_url}}"
        ),
        "body_html": (
            "<h2 style=\"color:#C9A84C;margin:0 0 16px;font-size:20px;\">{{promo_title}}</h2>"
            "<p style=\"color:#ccc;font-size:15px;line-height:1.6;\">{{promo_description}}</p>"
            "<div style=\"text-align:center;margin:24px 0;\">"
            "<a href=\"{{order_url}}\" style=\"display:inline-block;background:linear-gradient(135deg,#C9A84C,#e8c76a);"
            "color:#000;font-weight:800;padding:14px 32px;border-radius:10px;text-decoration:none;\">"
            "Zur Aktion bestellen</a></div>"
            "<p style=\"color:#555;font-size:11px;text-align:center;\">"
            "<a href=\"{{unsubscribe_url}}\" style=\"color:#666;\">Mails abbestellen</a></p>"
        ),
    },
    "upsell_drehspiess": {
        "subject": "Hast du unsere Drehspiess-Pizza schon probiert? – {{shop_name}}",
        "body_text": (
            "Hey {{name}}, kennst du das schon?\n\n"
            "Du bist ein Burger-Fan – das wissen wir. Aber hast du unsere Drehspiess-Pizza schon probiert?\n\n"
            "Jetzt ausprobieren: {{order_url}}"
        ),
        "body_html": "",
    },
    "upsell_ayran": {
        "subject": "Dein Essen + Ayran = perfekte Kombo – {{shop_name}}",
        "body_text": (
            "Noch etwas zum Trinken, {{name}}?\n\n"
            "Unser hausgemachter Ayran ist die perfekte Begleitung zu Shawarma und Doner – nur 2 EUR.\n\n"
            "Jetzt bestellen: {{order_url}}"
        ),
        "body_html": "",
    },
    "upsell_loyalty_reminder": {
        "subject": "Noch ein paar Stempel bis zum Gratis-Ayran! – {{shop_name}}",
        "body_text": (
            "Du bist fast da, {{name}}!\n\n"
            "Noch ein paar Bestellungen und du bekommst deinen hausgemachten Gratis-Ayran.\n\n"
            "Jetzt bestellen: {{order_url}}"
        ),
        "body_html": "",
    },
}


def ensure_schema(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS message_templates (
            key         TEXT PRIMARY KEY,
            channel     TEXT NOT NULL DEFAULT 'email',
            subject     TEXT NOT NULL DEFAULT '',
            body_html   TEXT NOT NULL DEFAULT '',
            updated_at  REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS marketing_send_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            email       TEXT NOT NULL,
            template    TEXT NOT NULL,
            created_at  REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_msl_email_time
            ON marketing_send_log(email, created_at);
        """
    )
    try:
        db.execute("ALTER TABLE message_templates ADD COLUMN body_text TEXT NOT NULL DEFAULT ''")
    except Exception:
        pass
    now = time.time()
    for key, tpl in DEFAULT_TEMPLATES.items():
        row = db.execute(
            "SELECT key, body_html, body_text FROM message_templates WHERE key=?", (key,)
        ).fetchone()
        body_html = tpl.get("body_html") or plain_to_html(tpl.get("body_text") or "")
        body_text = tpl.get("body_text") or html_to_plain(body_html)
        if not row:
            db.execute(
                "INSERT INTO message_templates (key, channel, subject, body_html, body_text, updated_at) VALUES (?,?,?,?,?,?)",
                (key, "email", tpl["subject"], body_html, body_text, now),
            )
        else:
            # backfill body_text if empty (Row oder Tuple – init_db ohne row_factory)
            try:
                existing_html = row["body_html"] if hasattr(row, "keys") else row[1]
                existing_text = (row["body_text"] if hasattr(row, "keys") else row[2]) or ""
            except Exception:
                existing_html, existing_text = "", ""
            existing_text = (existing_text or "").strip()
            if not existing_text:
                plain = html_to_plain(existing_html or "") or body_text
                db.execute(
                    "UPDATE message_templates SET body_text=? WHERE key=?",
                    (plain, key),
                )
    db.commit()


def email_wrapper(shop_name: str, content_html: str, *, footer_extra: str = "") -> str:
    """Snack-House-Branded Email-Hülle mit quadratischem Logo."""
    logo = SHOP_LOGO_URL
    return f"""<!DOCTYPE html>
<html lang="de"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#0a0806;font-family:Arial,Helvetica,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0806;padding:32px 0;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;background:#111008;border-radius:16px;overflow:hidden;border:1px solid #2a2318;">
        <tr>
          <td style="background:linear-gradient(135deg,#0f0d0a,#1a1410);padding:24px 32px;border-bottom:1px solid #2a2318;text-align:center;">
            <img src="{logo}" alt="{shop_name}" width="72" height="72"
                 style="display:block;margin:0 auto 12px;width:72px;height:72px;border-radius:14px;object-fit:cover;border:1px solid #2a2318;">
            <div style="font-size:20px;font-weight:900;color:#C9A84C;letter-spacing:.02em;">{shop_name}</div>
            <div style="font-size:11px;color:#555;margin-top:4px;letter-spacing:.08em;">Dr.-Felix-Gerhardus-Str. 7 · 53894 Mechernich</div>
          </td>
        </tr>
        <tr>
          <td style="padding:28px 32px;">
            {content_html}
          </td>
        </tr>
        <tr>
          <td style="background:#0e0b08;padding:20px 32px;border-top:1px solid #1e1a14;text-align:center;">
            <p style="margin:0;font-size:11px;color:#444;">Fragen? <a href="tel:024433088966" style="color:#C9A84C;text-decoration:none;">02443-3088966</a></p>
            <p style="margin:6px 0 0;font-size:10px;color:#333;">Mittwoch: Ruhetag · Online bestellen: <a href="{SHOP_ASSET_BASE}/bestellen" style="color:#555;text-decoration:none;">snackhouse-yassine.de</a></p>
            {footer_extra}
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def render_placeholders(text: str, ctx: dict[str, Any]) -> str:
    out = text or ""
    for k, v in ctx.items():
        out = out.replace("{{" + k + "}}", str(v if v is not None else ""))
    return out


def _tpl_public(row: dict | Any, key: str = "") -> dict[str, Any]:
    d = dict(row) if not isinstance(row, dict) else row
    k = d.get("key") or key
    body_html = d.get("body_html") or ""
    body_text = (d.get("body_text") or "").strip() or html_to_plain(body_html)
    if not body_html and body_text:
        body_html = plain_to_html(body_text)
    return {
        "key": k,
        "label": TEMPLATE_LABELS.get(k, k),
        "channel": d.get("channel") or "email",
        "subject": d.get("subject") or "",
        "body_text": body_text,
        "body_html": body_html,
        "updated_at": d.get("updated_at"),
    }


def get_template(db: sqlite3.Connection, key: str) -> dict[str, str]:
    ensure_schema(db)
    try:
        row = db.execute(
            "SELECT key, subject, body_html, body_text, channel, updated_at FROM message_templates WHERE key=?",
            (key,),
        ).fetchone()
    except Exception:
        row = db.execute(
            "SELECT key, subject, body_html, channel, updated_at FROM message_templates WHERE key=?",
            (key,),
        ).fetchone()
    if row:
        return _tpl_public(row, key)
    d = DEFAULT_TEMPLATES.get(key) or {"subject": key, "body_html": "", "body_text": ""}
    return _tpl_public({
        "key": key,
        "subject": d["subject"],
        "body_html": d.get("body_html") or plain_to_html(d.get("body_text") or ""),
        "body_text": d.get("body_text") or "",
        "channel": "email",
    }, key)


def list_templates(db: sqlite3.Connection) -> list[dict]:
    ensure_schema(db)
    try:
        rows = db.execute(
            "SELECT key, channel, subject, body_html, body_text, updated_at FROM message_templates ORDER BY key"
        ).fetchall()
    except Exception:
        rows = db.execute(
            "SELECT key, channel, subject, body_html, updated_at FROM message_templates ORDER BY key"
        ).fetchall()
    return [_tpl_public(r) for r in rows]


def save_template(
    db: sqlite3.Connection,
    key: str,
    subject: str,
    body_html: str = "",
    channel: str = "email",
    body_text: str | None = None,
) -> dict:
    ensure_schema(db)
    now = time.time()
    if body_text is not None and body_text.strip():
        plain = body_text.strip()
        html = plain_to_html(plain) if not (body_html or "").strip() else body_html
    else:
        html = body_html or ""
        plain = html_to_plain(html)
    db.execute(
        """INSERT INTO message_templates (key, channel, subject, body_html, body_text, updated_at)
           VALUES (?,?,?,?,?,?)
           ON CONFLICT(key) DO UPDATE SET
             channel=excluded.channel, subject=excluded.subject,
             body_html=excluded.body_html, body_text=excluded.body_text,
             updated_at=excluded.updated_at""",
        (key, channel, subject, html, plain, now),
    )
    db.commit()
    return get_template(db, key)


def rendered_body_html(db: sqlite3.Connection, key: str, ctx: dict[str, Any]) -> tuple[str, str]:
    """Subject + HTML body from template (prefers body_text → html)."""
    tpl = get_template(db, key)
    subject = render_placeholders(tpl["subject"], ctx)
    plain = (tpl.get("body_text") or "").strip()
    if plain:
        body = plain_to_html(render_placeholders(plain, ctx))
    else:
        body = render_placeholders(tpl.get("body_html") or "", ctx)
    return subject, body


def email_has_marketing_consent(db: sqlite3.Connection, email: str) -> bool:
    """True if any customer_account with this email has marketing_consent=1."""
    email = (email or "").strip().lower()
    if not email:
        return False
    row = db.execute(
        """SELECT 1 FROM customer_accounts
           WHERE lower(email)=? AND deleted_at IS NULL AND marketing_consent=1
           LIMIT 1""",
        (email,),
    ).fetchone()
    return bool(row)


def within_frequency_cap(
    db: sqlite3.Connection,
    email: str,
    *,
    days: int | None = None,
    exclude_template: str | None = None,
) -> bool:
    """True if a marketing mail was already sent within `days` (cap hit)."""
    ensure_schema(db)
    if days is None:
        try:
            row = db.execute("SELECT value FROM settings WHERE key='marketing_freq_days'").fetchone()
            days = int((row["value"] if row else None) or 3)
        except Exception:
            days = 3
    email = (email or "").strip().lower()
    if not email:
        return True
    since = time.time() - days * 86400
    if exclude_template:
        row = db.execute(
            """SELECT 1 FROM marketing_send_log
               WHERE lower(email)=? AND created_at>=? AND template!=?
               LIMIT 1""",
            (email, since, exclude_template),
        ).fetchone()
    else:
        row = db.execute(
            """SELECT 1 FROM marketing_send_log
               WHERE lower(email)=? AND created_at>=?
               LIMIT 1""",
            (email, since),
        ).fetchone()
    return bool(row)


def record_marketing_send(db: sqlite3.Connection, email: str, template: str) -> None:
    ensure_schema(db)
    db.execute(
        "INSERT INTO marketing_send_log (email, template, created_at) VALUES (?,?,?)",
        ((email or "").strip().lower(), template, time.time()),
    )


def marketing_recipients(db: sqlite3.Connection) -> list[dict[str, str]]:
    """Deduped list of emails with marketing_consent from customer_accounts."""
    ensure_schema(db)
    rows = db.execute(
        """SELECT id, email, display_name FROM customer_accounts
           WHERE deleted_at IS NULL AND marketing_consent=1
             AND email IS NOT NULL AND trim(email) != ''
           ORDER BY id"""
    ).fetchall()
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for r in rows:
        em = (r["email"] or "").strip().lower()
        if not em or em in seen:
            continue
        seen.add(em)
        cid = int(r["id"])
        out.append({
            "email": em,
            "name": r["display_name"] or "",
            "customer_id": str(cid),
            "customer_number": f"SHY-{cid:05d}",
            "unsubscribe_url": f"{SHOP_ASSET_BASE}/konto?unsubscribe=1",
        })
    return out


def unsubscribe_token_context(email: str) -> str:
    return f"{SHOP_ASSET_BASE}/konto?marketing=0&email={email}"


def build_promo_email(db: sqlite3.Connection, promo: dict, recipient: dict) -> tuple[str, str]:
    tpl = get_template(db, "promo_blast")
    desc = (promo.get("description") or "").strip()
    if not desc:
        free = promo.get("free_item_name") or ""
        trig = promo.get("trigger_value") or ""
        if free and trig:
            desc = f"Bei {trig}: {free} gratis"
        elif free:
            desc = f"{free} gratis zur Aktion"
    ctx = {
        "shop_name": SHOP_NAME,
        "name": recipient.get("name") or "du",
        "promo_title": promo.get("title") or "Sonderaktion",
        "promo_description": desc,
        "order_url": f"{SHOP_ASSET_BASE}/bestellen",
        "unsubscribe_url": recipient.get("unsubscribe_url")
        or unsubscribe_token_context(recipient.get("email") or ""),
        "review_url": "",
    }
    subject = render_placeholders(tpl["subject"], ctx)
    body = render_placeholders(tpl["body_html"], ctx)
    html = email_wrapper(SHOP_NAME, body)
    return subject, html


def default_ctx(**extra: Any) -> dict[str, Any]:
    base = {
        "shop_name": SHOP_NAME,
        "order_url": f"{SHOP_ASSET_BASE}/bestellen",
        "review_url": "",
        "name": "du",
        "unsubscribe_url": f"{SHOP_ASSET_BASE}/konto",
    }
    base.update(extra)
    return base
