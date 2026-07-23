"""Webschmiede seminar registration (capacity, waitlist-ready)."""
import json
import re

_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")


def init_schema(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS seminars (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            description TEXT,
            event_date  TEXT NOT NULL,
            event_time  TEXT,
            location    TEXT,
            max_seats   INTEGER NOT NULL DEFAULT 20,
            active      INTEGER NOT NULL DEFAULT 1,
            cal_link    TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS seminar_registrations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            seminar_id  INTEGER NOT NULL,
            name        TEXT NOT NULL,
            email       TEXT NOT NULL,
            phone       TEXT,
            company     TEXT,
            notes       TEXT,
            status      TEXT DEFAULT 'confirmed',
            created_at  TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (seminar_id) REFERENCES seminars(id)
        )
    """)
    row = db.execute("SELECT COUNT(*) FROM seminars").fetchone()
    if row and row[0] == 0:
        db.execute("""
            INSERT INTO seminars (title, description, event_date, event_time, location, max_seats, cal_link)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            "Gastro Digital: Online-Bestellen & Stammkunden",
            "Workshop für Restaurant-Inhaber: eigenes Bestellportal, Bonuskarte, SMS-Link bei Anruf, ohne Lieferando-Provision.",
            "2026-09-15",
            "18:00",
            "Online (Zoom), Link nach Anmeldung",
            20,
            "",
        ))


def _count_confirmed(db, seminar_id: int) -> int:
    row = db.execute(
        "SELECT COUNT(*) AS c FROM seminar_registrations WHERE seminar_id=? AND status='confirmed'",
        (seminar_id,),
    ).fetchone()
    return int(row["c"]) if row else 0


def seminar_public_row(db, row: dict) -> dict:
    sid = row["id"]
    taken = _count_confirmed(db, sid)
    max_s = int(row["max_seats"])
    return {
        "id": sid,
        "title": row["title"],
        "description": row.get("description") or "",
        "event_date": row["event_date"],
        "event_time": row.get("event_time") or "",
        "location": row.get("location") or "",
        "max_seats": max_s,
        "seats_taken": taken,
        "seats_left": max(0, max_s - taken),
        "full": taken >= max_s,
        "cal_link": row.get("cal_link") or "",
    }


def list_public(db) -> list:
    rows = db.execute(
        "SELECT * FROM seminars WHERE active=1 ORDER BY event_date ASC"
    ).fetchall()
    return [seminar_public_row(db, dict(r)) for r in rows]


def list_admin(db) -> list:
    out = []
    for r in db.execute("SELECT * FROM seminars ORDER BY event_date DESC").fetchall():
        d = dict(r)
        d.update({
            "seats_taken": _count_confirmed(db, d["id"]),
            "seats_left": max(0, int(d["max_seats"]) - _count_confirmed(db, d["id"])),
        })
        out.append(d)
    return out


def get_seminar(db, seminar_id: int) -> dict | None:
    row = db.execute("SELECT * FROM seminars WHERE id=?", (seminar_id,)).fetchone()
    return dict(row) if row else None


def register(db, seminar_id: int, data: dict) -> tuple[dict | None, str | None]:
    sem = get_seminar(db, seminar_id)
    if not sem or not sem.get("active"):
        return None, "Seminar nicht gefunden"
    if not sem["active"]:
        return None, "Anmeldung nicht mehr möglich"

    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    if not name or len(name) > 100:
        return None, "Name ungültig"
    if not email or not _EMAIL_RE.match(email):
        return None, "E-Mail ungültig"

    phone = (data.get("phone") or "").strip()[:30]
    company = (data.get("company") or "").strip()[:100]
    notes = (data.get("notes") or "").strip()[:500]

    if _count_confirmed(db, seminar_id) >= int(sem["max_seats"]):
        return None, "Leider ausgebucht. Warteliste folgt bald."

    dup = db.execute(
        "SELECT id FROM seminar_registrations WHERE seminar_id=? AND email=? AND status='confirmed'",
        (seminar_id, email),
    ).fetchone()
    if dup:
        return None, "Du bist bereits angemeldet."

    db.execute(
        """INSERT INTO seminar_registrations (seminar_id, name, email, phone, company, notes)
           VALUES (?,?,?,?,?,?)""",
        (seminar_id, name, email, phone, company, notes),
    )
    reg_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    pub = seminar_public_row(db, sem)
    return {
        "registration_id": reg_id,
        "seminar": pub,
        "name": name,
        "email": email,
    }, None


def list_registrations(db, seminar_id: int) -> list:
    rows = db.execute(
        "SELECT * FROM seminar_registrations WHERE seminar_id=? ORDER BY created_at DESC",
        (seminar_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def create_seminar(db, data: dict) -> int:
    cur = db.execute(
        """INSERT INTO seminars (title, description, event_date, event_time, location, max_seats, active, cal_link)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            data["title"],
            data.get("description", ""),
            data["event_date"],
            data.get("event_time", ""),
            data.get("location", ""),
            int(data.get("max_seats", 20)),
            1 if data.get("active", True) else 0,
            data.get("cal_link", ""),
        ),
    )
    return cur.lastrowid


def update_seminar(db, seminar_id: int, data: dict) -> bool:
    if not get_seminar(db, seminar_id):
        return False
    db.execute(
        """UPDATE seminars SET title=?, description=?, event_date=?, event_time=?,
           location=?, max_seats=?, active=?, cal_link=? WHERE id=?""",
        (
            data.get("title"),
            data.get("description", ""),
            data.get("event_date"),
            data.get("event_time", ""),
            data.get("location", ""),
            int(data.get("max_seats", 20)),
            1 if data.get("active", True) else 0,
            data.get("cal_link", ""),
            seminar_id,
        ),
    )
    return True


def cancel_registration(db, reg_id: int) -> bool:
    db.execute(
        "UPDATE seminar_registrations SET status='cancelled' WHERE id=?",
        (reg_id,),
    )
    return True
