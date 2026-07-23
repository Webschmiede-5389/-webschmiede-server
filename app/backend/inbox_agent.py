"""Agency inbox agent: classify, auto-reply, queue, digest, export."""
from __future__ import annotations

import csv
import io
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from email.utils import parseaddr
from pathlib import Path

FAQ_PATH = Path(__file__).resolve().parent.parent / "jarvis" / "inbox_faq.json"

STATUS_AUTO = "auto"
STATUS_PENDING = "pending"
STATUS_URGENT = "urgent"
STATUS_IGNORED = "ignored"
STATUS_MANUAL_DONE = "manual_done"


def _load_faq() -> dict:
    if FAQ_PATH.exists():
        return json.loads(FAQ_PATH.read_text(encoding="utf-8"))
    return {"faqs": [], "spam_keywords": [], "urgent_keywords": [], "pending_keywords": []}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _contains_any(text: str, keywords: list[str]) -> bool:
    t = _norm(text)
    return any(k in t for k in keywords)


def _score_faq(text: str, faq: dict) -> int:
    t = _norm(text)
    score = 0
    for kw in faq.get("keywords", []):
        if kw in t:
            score += 2 if " " in kw else 1
    return score


def classify_email(subject: str, body: str) -> dict:
    """Return status, category, faq_id, confidence."""
    combined = f"{subject}\n{body}"
    cfg = _load_faq()

    if _contains_any(combined, cfg.get("spam_keywords", [])):
        return {"status": STATUS_IGNORED, "category": "spam", "faq_id": None, "confidence": 0.9}

    if _contains_any(combined, cfg.get("urgent_keywords", [])):
        return {"status": STATUS_URGENT, "category": "urgent", "faq_id": None, "confidence": 0.85}

    best_id = None
    best_score = 0
    best_label = ""
    for faq in cfg.get("faqs", []):
        s = _score_faq(combined, faq)
        if s > best_score:
            best_score = s
            best_id = faq["id"]
            best_label = faq.get("label", faq["id"])

    if best_score >= 2:
        conf = min(0.95, 0.5 + best_score * 0.1)
        return {"status": STATUS_AUTO, "category": best_label, "faq_id": best_id, "confidence": conf}

    if _contains_any(combined, cfg.get("pending_keywords", [])) or "?" in combined:
        return {"status": STATUS_PENDING, "category": "unbekannt", "faq_id": None, "confidence": 0.5}

    return {"status": STATUS_PENDING, "category": "unbekannt", "faq_id": None, "confidence": 0.3}


def _faq_reply(faq_id: str) -> dict | None:
    for faq in _load_faq().get("faqs", []):
        if faq["id"] == faq_id:
            return faq
    return None


def _reply_subject(original: str, faq_subject: str) -> str:
    orig = (original or "").strip()
    if orig.lower().startswith("re:"):
        return faq_subject
    if len(orig) > 3:
        return f"Re: {orig}"
    return faq_subject


def _send_reply(*, to: str, subject: str, text: str, html: str) -> None:
    from agency_mail import send_html_email
    from email_templates import email_shell

    if "<html" not in (html or "").lower():
        html = email_shell(
            hero_title="Webschmiede",
            hero_subtitle=subject.replace("Re:", "").strip()[:80],
            preheader=(text or subject)[:120],
            body_html=html,
        )

    send_html_email(to=to, subject=subject, html=html, text=text)


def _send_urgent_alert(*, owner: str, from_email: str, subject: str, preview: str) -> None:
    from email_templates import email_link, email_shell
    from agency_mail import send_html_email

    body = f"""
    <p><strong>Dringende Agency-Mail</strong>, bitte heute bearbeiten:</p>
    <p><strong>Von:</strong> {from_email}<br><strong>Betreff:</strong> {subject}</p>
    <p style="background:#FFF4ED;padding:12px;border-radius:8px;font-size:14px;border:1px solid #FFD4B8;">{preview[:400]}</p>
    <p>{email_link("https://digitalehandwerkskunst.de/agency", "Posteingang öffnen")}</p>
    """
    html = email_shell(
        hero_title="Dringend: E-Mail",
        hero_subtitle=subject[:80],
        preheader=f"Dringend von {from_email}",
        body_html=body,
    )
    send_html_email(
        to=owner,
        subject=f"[Dringend] {subject[:60]}",
        html=html,
        text=f"Dringend von {from_email}: {subject}\n\n{preview[:400]}\n\n/agency",
    )


def process_incoming(db: sqlite3.Connection, payload: dict) -> dict:
    """Process one inbound email (called from n8n)."""
    message_id = (payload.get("message_id") or payload.get("messageId") or "").strip()
    if message_id:
        dup = db.execute(
            "SELECT id FROM inbox_log WHERE message_id=? LIMIT 1", (message_id,)
        ).fetchone()
        if dup:
            return {"ok": True, "duplicate": True, "id": dup["id"]}

    from_raw = payload.get("from") or payload.get("from_email") or ""
    _, from_email = parseaddr(from_raw)
    if not from_email:
        from_email = from_raw.strip()

    subject = (payload.get("subject") or "").strip()
    body = (payload.get("body_text") or payload.get("body") or payload.get("text") or "").strip()
    if not body and payload.get("body_html"):
        body = re.sub(r"<[^>]+>", " ", payload.get("body_html", ""))
    preview = body[:500] if body else subject[:500]

    clf = classify_email(subject, body)
    status = clf["status"]
    reply_sent = 0
    reply_subject = ""
    action = clf["category"]

    owner = os.getenv("AGENCY_OWNER_EMAIL", "")
    if not owner:
        _, secrets = _read_owner_from_secrets()
        owner = secrets

    if status == STATUS_AUTO and clf["faq_id"]:
        faq = _faq_reply(clf["faq_id"])
        if faq and from_email:
            reply_subject = _reply_subject(subject, faq["subject"])
            try:
                _send_reply(
                    to=from_email,
                    subject=reply_subject,
                    text=faq["reply_text"],
                    html=faq.get("reply_html") or f"<pre>{faq['reply_text']}</pre>",
                )
                reply_sent = 1
                action = f"auto:{faq['id']}"
            except Exception as e:
                status = STATUS_PENDING
                action = f"auto_failed:{str(e)[:80]}"

    elif status == STATUS_URGENT and owner:
        try:
            _send_urgent_alert(owner=owner, from_email=from_email, subject=subject, preview=preview)
            action = "urgent_alert_sent"
        except Exception as e:
            action = f"urgent_alert_failed:{str(e)[:80]}"

    received_at = payload.get("received_at") or datetime.now(timezone.utc).isoformat()

    cur = db.execute(
        """INSERT INTO inbox_log
           (received_at, message_id, from_email, from_name, subject, body_preview,
            status, category, faq_id, confidence, action_taken, reply_sent, reply_subject)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            received_at,
            message_id or None,
            from_email,
            (payload.get("from_name") or from_raw.split("<")[0].strip())[:120],
            subject[:500],
            preview,
            status,
            clf["category"],
            clf["faq_id"],
            clf["confidence"],
            action,
            reply_sent,
            reply_subject[:500] if reply_subject else None,
        ),
    )
    inbox_id = cur.lastrowid

    lead_info = None
    try:
        import agency_leads as leads_svc
        from_name = (payload.get("from_name") or from_raw.split("<")[0].strip())[:120]
        lead_info = leads_svc.upsert_from_inbound_email(
            db,
            from_email=from_email,
            from_name=from_name,
            subject=subject,
            body_preview=preview,
            inbox_id=inbox_id,
            inbox_status=status,
        )
        if lead_info:
            action = f"{action}|lead:{lead_info['id']}"
            db.execute(
                "UPDATE inbox_log SET action_taken=? WHERE id=?",
                (action[:200], inbox_id),
            )
    except Exception:
        pass

    db.commit()
    return {
        "ok": True,
        "id": inbox_id,
        "status": status,
        "category": clf["category"],
        "reply_sent": bool(reply_sent),
        "action": action,
        "lead": lead_info,
    }


def _read_owner_from_secrets() -> tuple[list[str], str]:
    path = Path("/root/app/deploy.secrets.local")
    if not path.exists():
        path = Path(__file__).resolve().parents[2] / "deploy.secrets.local"
    owner = ""
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("AGENCY_OWNER_EMAIL="):
                owner = line.split("=", 1)[1].strip()
    return [], owner


def list_inbox(db: sqlite3.Connection, *, day: str | None = None, status: str | None = None, limit: int = 200) -> list[dict]:
    q = "SELECT * FROM inbox_log WHERE 1=1"
    params: list = []
    if day == "today":
        q += " AND date(received_at) = date('now', 'localtime')"
    elif day:
        q += " AND date(received_at) = date(?)"
        params.append(day)
    if status:
        q += " AND status = ?"
        params.append(status)
    q += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    rows = db.execute(q, params).fetchall()
    return [dict(r) for r in rows]


def inbox_stats(db: sqlite3.Connection, *, day: str = "today") -> dict:
    if day == "today":
        date_filter = "date(received_at) = date('now', 'localtime')"
        params: tuple = ()
    else:
        date_filter = "date(received_at) = date(?)"
        params = (day,)
    rows = db.execute(
        f"""SELECT status, COUNT(*) AS n FROM inbox_log
            WHERE {date_filter} GROUP BY status""",
        params,
    ).fetchall()
    stats = {r["status"]: r["n"] for r in rows}
    total = sum(stats.values())
    return {
        "total": total,
        "auto": stats.get(STATUS_AUTO, 0),
        "pending": stats.get(STATUS_PENDING, 0),
        "urgent": stats.get(STATUS_URGENT, 0),
        "ignored": stats.get(STATUS_IGNORED, 0),
        "manual_done": stats.get(STATUS_MANUAL_DONE, 0),
    }


def update_inbox_item(db: sqlite3.Connection, item_id: int, *, status: str | None = None, notes: str | None = None) -> bool:
    row = db.execute("SELECT id FROM inbox_log WHERE id=?", (item_id,)).fetchone()
    if not row:
        return False
    if status:
        db.execute("UPDATE inbox_log SET status=?, updated_at=datetime('now') WHERE id=?", (status, item_id))
    if notes is not None:
        db.execute("UPDATE inbox_log SET notes=?, updated_at=datetime('now') WHERE id=?", (notes, item_id))
    db.commit()
    return True


def export_csv(db: sqlite3.Connection, *, day: str | None = None) -> str:
    rows = list_inbox(db, day=day, limit=5000)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow([
        "ID", "Empfangen", "Von", "Betreff", "Status", "Kategorie", "Auto-Antwort",
        "Aktion", "Notizen",
    ])
    status_de = {
        STATUS_AUTO: "Auto beantwortet",
        STATUS_PENDING: "Manuell offen",
        STATUS_URGENT: "Dringend",
        STATUS_IGNORED: "Ignoriert",
        STATUS_MANUAL_DONE: "Erledigt",
    }
    for r in rows:
        w.writerow([
            r.get("id"),
            r.get("received_at", ""),
            r.get("from_email", ""),
            r.get("subject", ""),
            status_de.get(r.get("status"), r.get("status")),
            r.get("category", ""),
            "Ja" if r.get("reply_sent") else "Nein",
            r.get("action_taken", ""),
            r.get("notes") or "",
        ])
    return buf.getvalue()


def send_evening_digest(db: sqlite3.Connection) -> dict:
    stats = inbox_stats(db, day="today")
    pending = list_inbox(db, day="today", status=STATUS_PENDING, limit=20)
    urgent = list_inbox(db, day="today", status=STATUS_URGENT, limit=20)

    owner = os.getenv("AGENCY_OWNER_EMAIL", "")
    if not owner:
        _, owner = _read_owner_from_secrets()
    if not owner:
        return {"ok": False, "error": "AGENCY_OWNER_EMAIL nicht gesetzt"}

    from email_templates import email_button, email_shell
    from agency_mail import send_html_email

    pending_rows = ""
    for p in pending[:10]:
        pending_rows += f"<li><strong>{p.get('from_email','')}</strong> · {p.get('subject','')[:60]}</li>"
    if not pending_rows:
        pending_rows = "<li>Keine offenen Mails</li>"

    urgent_rows = ""
    for u in urgent[:10]:
        urgent_rows += f"<li><strong>{u.get('from_email','')}</strong> · {u.get('subject','')[:60]}</li>"
    if not urgent_rows:
        urgent_rows = "<li>Keine dringenden Mails</li>"

    body = f"""
    <p>Ihr Tagesüberblick für den Agency-Posteingang:</p>
    <table role="presentation" style="width:100%;font-size:14px;margin:16px 0;">
      <tr><td style="padding:8px;background:#faf9f7;">Gesamt heute</td><td style="padding:8px;"><strong>{stats['total']}</strong></td></tr>
      <tr><td style="padding:8px;">Auto beantwortet</td><td style="padding:8px;color:#2ecc71;"><strong>{stats['auto']}</strong></td></tr>
      <tr><td style="padding:8px;">Manuell offen</td><td style="padding:8px;color:#FF6600;"><strong>{stats['pending']}</strong></td></tr>
      <tr><td style="padding:8px;">Dringend</td><td style="padding:8px;color:#e74c3c;"><strong>{stats['urgent']}</strong></td></tr>
      <tr><td style="padding:8px;">Ignoriert (Spam)</td><td style="padding:8px;">{stats['ignored']}</td></tr>
    </table>
    <h3 style="font-size:15px;margin:20px 0 8px;">Offen · manuell</h3>
    <ul style="margin:0;padding-left:20px;line-height:1.7;">{pending_rows}</ul>
    <h3 style="font-size:15px;margin:20px 0 8px;">Dringend</h3>
    <ul style="margin:0;padding-left:20px;line-height:1.7;">{urgent_rows}</ul>
    <p style="text-align:center;margin:24px 0;">
      {email_button("https://digitalehandwerkskunst.de/agency", "Posteingang öffnen")}
    </p>
    """
    html = email_shell(
        hero_title="Abend-Briefing Posteingang",
        hero_subtitle=datetime.now().strftime("%d.%m.%Y"),
        preheader=f"{stats['pending']} offen · {stats['urgent']} dringend · {stats['auto']} auto",
        body_html=body,
    )
    text = (
        f"Posteingang {datetime.now().strftime('%d.%m.%Y')}\n"
        f"Gesamt: {stats['total']} | Auto: {stats['auto']} | Offen: {stats['pending']} | Dringend: {stats['urgent']}\n"
        f"Dashboard: https://digitalehandwerkskunst.de/agency"
    )
    send_html_email(
        to=owner,
        subject=f"Posteingang heute · {stats['pending']} offen, {stats['urgent']} dringend",
        html=html,
        text=text,
    )
    return {"ok": True, "sent_to": owner, **stats}
