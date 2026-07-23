"""Agency-Leads aus Posteingang (E-Mail-Anfragen → Kontakt)."""
from __future__ import annotations

import json
import re
import sqlite3
from email.utils import parseaddr
from pathlib import Path
import os

IGNORE_FROM = (
    "noreply", "no-reply", "mailer-daemon", "postmaster",
    "newsletter", "donotreply", "do-not-reply",
)
INTERNAL_DOMAINS = ("digitalehandwerkskunst.de", "webschmiede.de")


def _split_name(from_name: str, from_email: str) -> str:
    name = (from_name or "").strip().strip('"')
    if name and "@" not in name:
        return name[:120]
    local = (from_email or "").split("@")[0]
    local = re.sub(r"[._+-]+", " ", local).strip()
    return local.title()[:120] if local else from_email


def _extract_phone(text: str) -> str:
    if not text:
        return ""
    patterns = [
        r"\+49[\d\s\-/]{8,18}",
        r"0\d{2,4}[\s\-/]?\d{3,12}",
        r"\b017[0-9][\d\s\-/]{6,12}\b",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return re.sub(r"[\s\-/]", "", m.group(0))[:24]
    return ""


def _is_skip_email(email: str) -> bool:
    e = (email or "").lower().strip()
    if not e or "@" not in e:
        return True
    local, domain = e.split("@", 1)
    if any(x in local for x in IGNORE_FROM):
        return True
    if any(domain.endswith(d) for d in INTERNAL_DOMAINS):
        return True
    return False


def _email_is_existing_kunde(email: str) -> bool:
    e = email.lower().strip()
    kdir = Path(os.getenv("KUNDEN_DIR", Path(__file__).resolve().parents[1] / "kunden"))
    if not kdir.is_dir():
        return False
    for p in kdir.glob("*.json"):
        k = json.loads(p.read_text(encoding="utf-8"))
        kontakt = (k.get("kontakt") or {}).get("email", "")
        if kontakt and kontakt.lower().strip() == e:
            return True
    return False


def ensure_table(db: sqlite3.Connection) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS agency_leads (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            email           TEXT UNIQUE NOT NULL,
            name            TEXT,
            phone           TEXT,
            company         TEXT,
            source          TEXT DEFAULT 'email',
            status          TEXT DEFAULT 'lead',
            inbox_id        INTEGER,
            subject         TEXT,
            body_preview    TEXT,
            notes           TEXT,
            converted_kunde_id TEXT,
            created_at      TEXT DEFAULT (datetime('now')),
            updated_at      TEXT DEFAULT (datetime('now'))
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_agency_leads_status ON agency_leads(status)")


def upsert_from_inbound_email(
    db: sqlite3.Connection,
    *,
    from_email: str,
    from_name: str,
    subject: str,
    body_preview: str,
    inbox_id: int,
    inbox_status: str,
) -> dict | None:
    """Neuen Lead anlegen oder bestehenden aktualisieren (nicht bei Spam)."""
    if inbox_status == "ignored":
        return None

    _, email = parseaddr(from_email)
    email = (email or from_email or "").strip().lower()
    if _is_skip_email(email) or _email_is_existing_kunde(email):
        return None

    ensure_table(db)
    name = _split_name(from_name, email) if (from_name or "").strip() else ""
    phone = _extract_phone(body_preview or "")
    subject = (subject or "")[:500]
    preview = (body_preview or "")[:500]

    row = db.execute(
        "SELECT id, name, phone FROM agency_leads WHERE email=? COLLATE NOCASE",
        (email,),
    ).fetchone()

    if row:
        stored_name = name or row["name"]
        db.execute(
            """UPDATE agency_leads SET
               name=COALESCE(NULLIF(?, ''), name),
               phone=COALESCE(NULLIF(?, ''), phone),
               inbox_id=?, subject=?, body_preview=?,
               updated_at=datetime('now')
               WHERE id=?""",
            (name, phone, inbox_id, subject, preview, row["id"]),
        )
        db.commit()
        return {"id": row["id"], "email": email, "created": False, "name": stored_name}

    cur = db.execute(
        """INSERT INTO agency_leads
           (email, name, phone, source, status, inbox_id, subject, body_preview)
           VALUES (?,?,?,?,?,?,?,?)""",
        (email, name or _split_name("", email), phone or None, "email", "lead", inbox_id, subject, preview),
    )
    db.commit()
    return {"id": cur.lastrowid, "email": email, "created": True, "name": name}


def list_leads(db: sqlite3.Connection, *, status: str | None = None, limit: int = 100) -> list[dict]:
    ensure_table(db)
    q = "SELECT * FROM agency_leads WHERE converted_kunde_id IS NULL OR converted_kunde_id = ''"
    params: list = []
    if status:
        q += " AND status=?"
        params.append(status)
    q += " ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)
    return [dict(r) for r in db.execute(q, params).fetchall()]


def get_lead(db: sqlite3.Connection, lead_id: int) -> dict | None:
    ensure_table(db)
    row = db.execute("SELECT * FROM agency_leads WHERE id=?", (lead_id,)).fetchone()
    return dict(row) if row else None


def mark_converted(db: sqlite3.Connection, lead_id: int, kunde_id: str) -> bool:
    ensure_table(db)
    cur = db.execute(
        """UPDATE agency_leads SET converted_kunde_id=?, status='converted',
           updated_at=datetime('now') WHERE id=?""",
        (kunde_id.upper(), lead_id),
    )
    db.commit()
    return cur.rowcount > 0


def convert_lead(db: sqlite3.Connection, lead_id: int, kunde_id: str) -> dict:
    """Lead als umgewandelt markieren (Kunde wurde separat angelegt)."""
    lead = get_lead(db, lead_id)
    if not lead:
        raise ValueError("Kontakt nicht gefunden")
    if lead.get("converted_kunde_id"):
        raise ValueError(f"Bereits Kunde {lead['converted_kunde_id']}")
    kid = (kunde_id or "").upper().strip()
    if not kid:
        raise ValueError("kunde_id fehlt")
    mark_converted(db, lead_id, kid)
    return {"ok": True, "lead_id": lead_id, "kunde_id": kid}
