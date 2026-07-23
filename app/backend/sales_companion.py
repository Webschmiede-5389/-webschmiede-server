"""Sales-Begleiter: Christian bei jedem Funnel-Schritt informieren + erinnern.

Kanäle: E-Mail (Pflicht), WhatsApp an OWNER_PHONE wenn Meta-Token da.
Kein Spam: gleicher Stage nur einmal, Reminder mit Cooldown.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SITE = "https://digitalehandwerkskunst.de"
DASH = f"{SITE}/sales-dashboard.html"
STATE_DIR_DIGEST = Path(
    os.getenv(
        "SALES_DIGEST_MARKER",
        str(Path(__file__).resolve().parent.parent / "vault" / "sales" / "digest_marker.txt"),
    )
)

# stage -> (kurz WhatsApp/Betreff-Kern, Mail-Body, nächster Schritt für dich)
STAGES: dict[str, dict[str, str]] = {
    "meeting_scan": {
        "title": "Meeting-Scan fertig",
        "body": "Website/Firma gescannt, Pain-Angebot liegt als Entwurf.",
        "next": "Entwurf prüfen, dann Einladung oder Freigabe Pain-Mail.",
    },
    "invited": {
        "title": "Einladung raus",
        "body": "Die Onboarding-Mail ist an den Kunden raus. Warte aufs Ausfüllen.",
        "next": "Wenn er nicht innerhalb 1–2 Tagen startet: kurz nachfassen (Anruf/WhatsApp).",
    },
    "website_lead": {
        "title": "Website-Lead rein",
        "body": "Jemand hat sich über die Website gemeldet. Discovery-Mail ist raus.",
        "next": "Deal im Dashboard anschauen, bei Bedarf anrufen.",
    },
    "discovery_started": {
        "title": "Kunde hat angefangen",
        "body": "Der Kunde hat das Formular geöffnet / Firmendaten eingetragen.",
        "next": "Nichts tun. Wenn er steckenbleibt, erinnert dich der Reminder.",
    },
    "discovery_answers": {
        "title": "Fragen ausgefüllt",
        "body": "Tools und Fragen sind drin. Als Nächstes baue ich die Einschätzung.",
        "next": "Gleich kommt die Pain-Einschätzung an den Kunden (ohne Preis).",
    },
    "awaiting_freigabe_pain": {
        "title": "Freigabe nötig: Einschätzung",
        "body": "Research und Entwurf sind fertig. Die Kunden-Mail wartet auf dein OK.",
        "next": "Dashboard → Freigabe. Bei Unsicherheit Entwurf lesen, dann senden oder zurückhalten.",
    },
    "reminder_freigabe_pain": {
        "title": "Erinnerung: Freigabe offen",
        "body": "Die Einschätzung liegt noch bei dir. Kunde wartet auf die Mail.",
        "next": "Dashboard → Freigabe oder Halten.",
    },
    "pain_offer_sent": {
        "title": "Einschätzung an Kunden",
        "body": "Pain-Einschätzung ohne Preis ist nach Freigabe per Mail raus.",
        "next": "Im Dashboard den Preis setzen, sobald er „passt“ sagt oder du pushen willst.",
    },
    "need_price": {
        "title": "Preis fehlt noch",
        "body": "Kunde ist soweit, aber ohne deinen Preis geht kein Checkout.",
        "next": "Sales-Dashboard → Preis → Angebot mit Zahlen senden.",
    },
    "offer_sent": {
        "title": "Angebot mit Preis raus",
        "body": "Beziffertes Angebot ist an den Kunden.",
        "next": "Warten auf „Passt“ / Checkout. Vertrag (DocuSeal) parallel anstoßen.",
    },
    "checkout": {
        "title": "Zahlungslink bereit",
        "body": "Kunde will bestellen. Stripe-Link ist raus bzw. bereit.",
        "next": "DocuSeal-Vertrag nachziehen falls noch offen. Bei Stocken nachfassen.",
    },
    "accept_need_price": {
        "title": "Kunde will, Preis fehlt",
        "body": "Kunde hat auf Bestellen geklickt, aber der Preis ist noch nicht gesetzt.",
        "next": "Sofort Preis setzen und Checkout erneut auslösen.",
    },
    "reminder_invited": {
        "title": "Erinnerung: Formular offen",
        "body": "Der Kunde hat die Einladung noch nicht durchgezogen.",
        "next": "Kurz schreiben oder anrufen: Link nochmal schicken reicht oft.",
    },
    "reminder_offer_draft": {
        "title": "Erinnerung: Preis setzen",
        "body": "Einschätzung ist raus, Preis/Angebot von dir fehlt noch.",
        "next": "Dashboard öffnen und Setup/Monat eintragen.",
    },
    "reminder_offer_sent": {
        "title": "Erinnerung: Kunde zögert",
        "body": "Angebot liegt beim Kunden, noch kein Checkout.",
        "next": "Nachfassen: Passt der Preis? Vertrag erklären.",
    },
    "reminder_checkout": {
        "title": "Erinnerung: Zahlung offen",
        "body": "Zahlungslink liegt, Zahlung noch nicht durch.",
        "next": "Nachfassen oder Link nochmal schicken.",
    },
    "reminder_contract": {
        "title": "Erinnerung: Vertrag",
        "body": "Deal läuft, DocuSeal-Vertrag ggf. noch nicht unterschrieben.",
        "next": "Vertragspaket senden / Status in DocuSeal prüfen.",
    },
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_s() -> str:
    return _now().strftime("%Y-%m-%dT%H:%M:%SZ")


def _owner_email() -> str:
    try:
        from agency_mail import _read_secrets

        sec = _read_secrets()
    except Exception:
        sec = {}
    return (
        os.getenv("AGENCY_OWNER_EMAIL")
        or sec.get("AGENCY_OWNER_EMAIL")
        or sec.get("AGENCY_SMTP_USER")
        or ""
    ).strip()


def _owner_phone() -> str:
    for key in ("OWNER_PHONE", "AGENCY_OWNER_PHONE", "NILS_OPS_OWNER_PHONES"):
        raw = (os.getenv(key) or "").strip()
        if raw:
            return raw.split(",")[0].strip()
    try:
        from agency_mail import _read_secrets

        sec = _read_secrets()
        for key in ("OWNER_PHONE", "AGENCY_OWNER_PHONE", "NILS_OPS_OWNER_PHONES"):
            raw = (sec.get(key) or "").strip()
            if raw:
                return raw.split(",")[0].strip()
    except Exception:
        pass
    return ""


def _already_sent(deal: dict[str, Any], stage: str, *, hours: float = 0) -> bool:
    meta = deal.get("meta") if isinstance(deal.get("meta"), dict) else {}
    log = meta.get("notify_log") or {}
    last = log.get(stage)
    if not last:
        return False
    if hours <= 0:
        return True
    try:
        last_dt = datetime.fromisoformat(str(last).replace("Z", "+00:00"))
        return _now() - last_dt < timedelta(hours=hours)
    except ValueError:
        return True


def _mark_sent(db: sqlite3.Connection | None, deal: dict[str, Any], stage: str) -> None:
    if not db or not deal.get("id"):
        return
    meta = dict(deal.get("meta") or {}) if isinstance(deal.get("meta"), dict) else {}
    log = dict(meta.get("notify_log") or {})
    log[stage] = _now_s()
    meta["notify_log"] = log
    meta["last_ping"] = stage
    try:
        db.execute(
            "UPDATE sales_deals SET meta_json=?, updated_at=updated_at WHERE id=?",
            (json.dumps(meta, ensure_ascii=False), deal["id"]),
        )
        db.commit()
        deal["meta"] = meta
    except Exception:
        pass


def ping_owner(
    deal: dict[str, Any],
    *,
    stage: str,
    db: sqlite3.Connection | None = None,
    extra: str = "",
    force: bool = False,
    dedupe_hours: float = 0,
) -> dict[str, Any]:
    """Christian per Mail + optional WhatsApp/Telegram über Funnel-Schritt informieren."""
    if not force and _already_sent(deal, stage, hours=dedupe_hours):
        return {"ok": True, "skipped": True, "reason": "already_notified", "stage": stage}

    info = STAGES.get(stage) or {
        "title": stage,
        "body": f"Update: {stage}",
        "next": f"Dashboard: {DASH}",
    }
    firma = deal.get("firma") or deal.get("email") or "Deal"
    subject = f"[Funnel] {info['title']} · {firma}"
    text = (
        f"{info['title']}\n\n"
        f"{info['body']}\n"
        f"{extra.strip() + chr(10) if extra else ''}\n"
        f"Firma: {firma}\n"
        f"Kunde: {deal.get('email')}\n"
        f"Status: {deal.get('status')}\n"
        f"Deal: {deal.get('id')}\n"
        f"Nächster Schritt für dich: {info['next']}\n"
        f"Dashboard: {DASH}\n"
    )
    html = f"""
    <p><strong>{info['title']}</strong></p>
    <p>{info['body']}</p>
    {"<p>" + extra + "</p>" if extra else ""}
    <ul>
      <li>Firma: {firma}</li>
      <li>Mail: {deal.get('email')}</li>
      <li>Status: {deal.get('status')}</li>
      <li>Deal: {deal.get('id')}</li>
    </ul>
    <p><strong>Dein nächster Schritt:</strong> {info['next']}</p>
    <p><a href="{DASH}">Sales-Dashboard öffnen</a></p>
    """

    channels: dict[str, Any] = {}
    to = _owner_email()
    if to:
        try:
            from agency_mail import send_html_email
            from email_templates import email_shell

            full = email_shell(
                hero_title=info["title"],
                hero_subtitle=str(firma)[:80],
                preheader=subject[:120],
                body_html=html,
            )
            send_html_email(to=to, subject=subject, html=full, text=text)
            channels["email"] = {"ok": True, "to": to}
        except Exception as e:
            channels["email"] = {"ok": False, "error": str(e)[:160]}
    else:
        channels["email"] = {"ok": False, "error": "AGENCY_OWNER_EMAIL fehlt"}

    phone = _owner_phone()
    if phone:
        wa_text = (
            f"Funnel: {info['title']}\n"
            f"{firma} · {deal.get('email')}\n"
            f"{info['body']}\n"
            f"→ {info['next']}\n"
            f"{DASH}"
        )[:900]
        try:
            import messaging as msg

            channels["whatsapp"] = msg.send_whatsapp_text(phone, wa_text)
        except Exception as e:
            channels["whatsapp"] = {"ok": False, "error": str(e)[:160]}
    else:
        channels["whatsapp"] = {
            "ok": False,
            "skipped": True,
            "detail": "OWNER_PHONE setzen für WhatsApp-Pings",
        }

    short = (
        f"Funnel: {info['title']}\n"
        f"{firma} · {deal.get('email')}\n"
        f"{info['body']}\n"
        f"→ {info['next']}\n"
        f"{DASH}"
    )[:900]
    try:
        import telegram_ops as tg

        channels["telegram"] = tg.notify_owner(short)
    except Exception as e:
        channels["telegram"] = {"ok": False, "error": str(e)[:160]}

    ok = bool(
        (channels.get("email") or {}).get("ok")
        or (channels.get("whatsapp") or {}).get("ok")
        or (channels.get("telegram") or {}).get("ok")
    )
    if ok:
        _mark_sent(db, deal, stage)
    return {"ok": ok, "stage": stage, "channels": channels}


def run_reminders(db: sqlite3.Connection) -> dict[str, Any]:
    """Hängende Deals → Erinnerung an Christian (Cron alle paar Stunden)."""
    import sales_pipeline as sales

    sales.ensure_tables(db)
    rows = db.execute(
        """
        SELECT * FROM sales_deals
        WHERE status NOT IN ('paid', 'done', 'lost')
        ORDER BY datetime(updated_at) ASC
        LIMIT 80
        """
    ).fetchall()
    sent: list[dict[str, Any]] = []
    now = _now()
    for r in rows:
        deal = sales._row(r)  # noqa: SLF001
        if not deal:
            continue
        status = deal.get("status") or ""
        try:
            updated = datetime.fromisoformat(
                str(deal.get("updated_at") or "").replace(" ", "T")
            )
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
        except ValueError:
            updated = now - timedelta(days=2)
        age_h = (now - updated).total_seconds() / 3600.0

        stage = None
        if status == "invited" and age_h >= 24:
            stage = "reminder_invited"
        elif status == "awaiting_freigabe_pain" and age_h >= 4:
            stage = "reminder_freigabe_pain"
        elif status == "offer_draft" and age_h >= 8:
            stage = "reminder_offer_draft"
        elif status in ("priced", "offer_sent") and age_h >= 48:
            stage = "reminder_offer_sent"
        elif status == "checkout" and age_h >= 24:
            stage = "reminder_checkout"
        # Vertragshinweis wenn Angebot/Checkout länger läuft
        elif status in ("offer_sent", "checkout") and age_h >= 12:
            # nur wenn contract reminder noch nicht kürzlich
            if not _already_sent(deal, "reminder_contract", hours=48):
                stage = "reminder_contract"

        if not stage:
            continue
        # Reminder-Cooldownup 20h
        if _already_sent(deal, stage, hours=20):
            continue
        result = ping_owner(deal, stage=stage, db=db, force=True)
        sent.append({"deal_id": deal.get("id"), "stage": stage, "result": result.get("ok")})

    return {"ok": True, "reminders": len(sent), "items": sent, "as_of": _now_s()}


def digest(db: sqlite3.Connection) -> dict[str, Any]:
    """Kurzer Tagesstand für Christian (max 1× / 20h)."""
    import sales_pipeline as sales

    sales.ensure_tables(db)
    rows = db.execute(
        """
        SELECT status, COUNT(*) AS n FROM sales_deals
        WHERE status NOT IN ('lost')
        GROUP BY status
        """
    ).fetchall()
    counts = {dict(r)["status"]: dict(r)["n"] for r in rows}
    open_n = sum(v for k, v in counts.items() if k not in ("paid", "done"))
    lines = [f"Offene Deals: {open_n}"]
    for k, v in sorted(counts.items()):
        lines.append(f"  {k}: {v}")
    # Top 5 offene Deals
    open_rows = db.execute(
        """
        SELECT id, firma, email, status, updated_at FROM sales_deals
        WHERE status NOT IN ('paid', 'done', 'lost')
        ORDER BY datetime(updated_at) ASC LIMIT 5
        """
    ).fetchall()
    if open_rows:
        lines.append("")
        lines.append("Als Nächstes anfassen:")
        for r in open_rows:
            d = dict(r)
            lines.append(f"- {d.get('firma') or d.get('email')} ({d.get('status')})")
    lines.append("")
    lines.append(f"Dashboard: {DASH}")
    text = "\n".join(lines)

    marker = STATE_DIR_DIGEST
    if marker.is_file():
        try:
            last = datetime.fromisoformat(marker.read_text(encoding="utf-8").strip())
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if _now() - last < timedelta(hours=20):
                return {"ok": True, "skipped": True, "counts": counts}
        except Exception:
            pass

    to = _owner_email()
    if not to:
        return {"ok": False, "error": "AGENCY_OWNER_EMAIL fehlt", "counts": counts}
    try:
        from agency_mail import send_html_email
        from email_templates import email_shell

        html = email_shell(
            hero_title="Sales-Pipeline Tagesstand",
            hero_subtitle=_now_s(),
            body_html=f"<pre style='font-family:system-ui'>{text}</pre>",
        )
        send_html_email(
            to=to,
            subject=f"[Funnel] Tagesstand · {open_n} offen",
            html=html,
            text=text,
        )
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(_now().isoformat(), encoding="utf-8")
        # WhatsApp / Telegram Kurz
        phone = _owner_phone()
        wa = None
        tg_out = None
        digest_short = (
            f"Funnel-Tagesstand: {open_n} offen.\n" + "\n".join(lines[1:6]) + f"\n{DASH}"
        )
        if phone and open_n:
            try:
                import messaging as msg

                wa = msg.send_whatsapp_text(phone, digest_short)
            except Exception as e:
                wa = {"ok": False, "error": str(e)[:120]}
        if open_n:
            try:
                import telegram_ops as tg

                tg_out = tg.notify_owner(digest_short)
            except Exception as e:
                tg_out = {"ok": False, "error": str(e)[:120]}
        return {"ok": True, "counts": counts, "text": text, "whatsapp": wa, "telegram": tg_out}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160], "counts": counts}
