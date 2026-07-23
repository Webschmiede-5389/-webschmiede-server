"""Portal-Auth: Users, gehashte Passwörter, Sessions (SQLite), Reset, TOTP-Basis.

Rollen: agency | kunde_admin
Sessions in DB (überlebt Restart + mehrere Gunicorn-Worker).
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from typing import Any

from werkzeug.security import check_password_hash, generate_password_hash

SESSION_TTL = int(os.getenv("AUTH_SESSION_TTL", str(12 * 3600)))
RESET_TTL = int(os.getenv("AUTH_RESET_TTL", str(60 * 60)))  # 1h


def ensure_schema(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS portal_users (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          username TEXT NOT NULL UNIQUE COLLATE NOCASE,
          email TEXT,
          password_hash TEXT NOT NULL,
          role TEXT NOT NULL DEFAULT 'agency',
          kunde_id TEXT,
          totp_secret TEXT,
          totp_enabled INTEGER NOT NULL DEFAULT 0,
          reset_token_hash TEXT,
          reset_expires REAL,
          created_at REAL NOT NULL,
          updated_at REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_portal_users_email ON portal_users(email);
        CREATE TABLE IF NOT EXISTS auth_sessions (
          token TEXT PRIMARY KEY,
          user_id INTEGER,
          kind TEXT NOT NULL,
          created_at REAL NOT NULL,
          expires_at REAL NOT NULL,
          FOREIGN KEY(user_id) REFERENCES portal_users(id)
        );
        CREATE INDEX IF NOT EXISTS idx_auth_sessions_exp ON auth_sessions(expires_at);
        """
    )
    db.commit()


def seed_bootstrap_users(
    db: sqlite3.Connection,
    *,
    agency_password: str,
    admin_password: str = "",
    agency_email: str = "",
) -> dict[str, Any]:
    """Legt Default-User an, wenn noch keine Agency-User existieren."""
    ensure_schema(db)
    created: list[str] = []
    now = time.time()
    row = db.execute(
        "SELECT id FROM portal_users WHERE role = 'agency' LIMIT 1"
    ).fetchone()
    if not row and agency_password:
        uname = (os.getenv("AGENCY_BOOTSTRAP_USER") or "christian").strip().lower()
        db.execute(
            """
            INSERT INTO portal_users
              (username, email, password_hash, role, kunde_id, totp_enabled, created_at, updated_at)
            VALUES (?, ?, ?, 'agency', NULL, 0, ?, ?)
            """,
            (
                uname,
                (agency_email or os.getenv("AGENCY_OWNER_EMAIL") or "").strip().lower() or None,
                generate_password_hash(agency_password),
                now,
                now,
            ),
        )
        created.append(f"agency:{uname}")
    # Kunden-Admin Bootstrap (SHY001 Shared-Admin), optional
    if admin_password:
        crow = db.execute(
            "SELECT id FROM portal_users WHERE role = 'kunde_admin' AND username = ? LIMIT 1",
            ("admin",),
        ).fetchone()
        if not crow:
            db.execute(
                """
                INSERT INTO portal_users
                  (username, email, password_hash, role, kunde_id, totp_enabled, created_at, updated_at)
                VALUES (?, NULL, ?, 'kunde_admin', ?, 0, ?, ?)
                """,
                (
                    "admin",
                    generate_password_hash(admin_password),
                    os.getenv("DEFAULT_KUNDE_ID", "SHY001"),
                    now,
                    now,
                ),
            )
            created.append("kunde_admin:admin")
    if created:
        db.commit()
    return {"created": created}


def get_user_by_username(db: sqlite3.Connection, username: str) -> dict[str, Any] | None:
    row = db.execute(
        "SELECT * FROM portal_users WHERE username = ? COLLATE NOCASE LIMIT 1",
        ((username or "").strip(),),
    ).fetchone()
    return dict(row) if row else None


def get_user_by_id(db: sqlite3.Connection, user_id: int) -> dict[str, Any] | None:
    row = db.execute("SELECT * FROM portal_users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def verify_password(user: dict[str, Any], password: str) -> bool:
    if not user or not password:
        return False
    try:
        return check_password_hash(user["password_hash"], password)
    except Exception:
        return False


def _legacy_pw_ok(provided: str, expected: str) -> bool:
    if not provided or not expected:
        return False
    return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


def create_session(
    db: sqlite3.Connection,
    *,
    kind: str,
    user_id: int | None = None,
    ttl: int | None = None,
) -> str:
    ensure_schema(db)
    token = secrets.token_hex(32)
    now = time.time()
    exp = now + float(ttl or SESSION_TTL)
    db.execute(
        "INSERT INTO auth_sessions (token, user_id, kind, created_at, expires_at) VALUES (?,?,?,?,?)",
        (token, user_id, kind, now, exp),
    )
    db.commit()
    return token


def destroy_session(db: sqlite3.Connection, token: str) -> None:
    if not token:
        return
    db.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
    db.commit()


def get_session(db: sqlite3.Connection, token: str) -> dict[str, Any] | None:
    if not token:
        return None
    ensure_schema(db)
    row = db.execute(
        "SELECT * FROM auth_sessions WHERE token = ? LIMIT 1", (token,)
    ).fetchone()
    if not row:
        return None
    sess = dict(row)
    if time.time() > float(sess["expires_at"]):
        db.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
        db.commit()
        return None
    return sess


def purge_expired(db: sqlite3.Connection) -> int:
    cur = db.execute("DELETE FROM auth_sessions WHERE expires_at < ?", (time.time(),))
    db.commit()
    return cur.rowcount or 0


def authenticate(
    db: sqlite3.Connection,
    *,
    username: str,
    password: str,
    role: str | None = None,
    legacy_agency_password: str = "",
    legacy_admin_password: str = "",
) -> dict[str, Any]:
    """Login. Unterstützt User-DB + Legacy-Shared-Passwort (Migration)."""
    ensure_schema(db)
    uname = (username or "").strip()
    pw = password or ""

    if uname:
        user = get_user_by_username(db, uname)
        if user and verify_password(user, pw):
            if role and user.get("role") != role:
                return {"ok": False, "error": "wrong_role"}
            return {"ok": True, "user": user, "via": "user"}
        # Secrets-Passwort geändert, Hash in DB noch alt → Agency-Login mit Legacy-PW erlauben
        if (
            user
            and user.get("role") == "agency"
            and (not role or role == "agency")
            and legacy_agency_password
            and _legacy_pw_ok(pw, legacy_agency_password)
        ):
            try:
                set_password(db, int(user["id"]), pw)
            except ValueError:
                pass
            user = get_user_by_username(db, uname) or user
            return {"ok": True, "user": user, "via": "legacy_agency_sync"}

    # Legacy: nur Passwort, kein Username → Agency Shared-PW
    if not uname and legacy_agency_password and _legacy_pw_ok(pw, legacy_agency_password):
        user = db.execute(
            "SELECT * FROM portal_users WHERE role = 'agency' ORDER BY id LIMIT 1"
        ).fetchone()
        if user:
            return {"ok": True, "user": dict(user), "via": "legacy_agency"}
        # noch kein User → seed + login
        seed_bootstrap_users(db, agency_password=legacy_agency_password)
        user = db.execute(
            "SELECT * FROM portal_users WHERE role = 'agency' ORDER BY id LIMIT 1"
        ).fetchone()
        if user:
            return {"ok": True, "user": dict(user), "via": "legacy_agency_seed"}

    if (
        (not uname or uname.lower() == "admin")
        and legacy_admin_password
        and _legacy_pw_ok(pw, legacy_admin_password)
    ):
        user = get_user_by_username(db, "admin")
        if not user:
            seed_bootstrap_users(
                db, agency_password="", admin_password=legacy_admin_password
            )
            user = get_user_by_username(db, "admin")
        if user and (not role or user.get("role") == role or role == "kunde_admin"):
            return {"ok": True, "user": user, "via": "legacy_admin"}

    return {"ok": False, "error": "invalid_credentials"}


def set_password(db: sqlite3.Connection, user_id: int, new_password: str) -> None:
    if len(new_password or "") < 10:
        raise ValueError("Passwort mindestens 10 Zeichen")
    db.execute(
        "UPDATE portal_users SET password_hash = ?, reset_token_hash = NULL, reset_expires = NULL, updated_at = ? WHERE id = ?",
        (generate_password_hash(new_password), time.time(), user_id),
    )
    db.commit()


def start_password_reset(db: sqlite3.Connection, username_or_email: str) -> dict[str, Any]:
    """Erzeugt Reset-Token. Gibt token nur zurück wenn User gefunden (Caller mailt)."""
    ensure_schema(db)
    q = (username_or_email or "").strip()
    if not q:
        return {"ok": False, "error": "empty"}
    row = db.execute(
        """
        SELECT * FROM portal_users
        WHERE username = ? COLLATE NOCASE OR lower(email) = lower(?)
        LIMIT 1
        """,
        (q, q),
    ).fetchone()
    # Immer gleiche Antwort nach außen (Timing/Enumeration) – Caller entscheidet
    if not row:
        return {"ok": True, "found": False}
    user = dict(row)
    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    db.execute(
        "UPDATE portal_users SET reset_token_hash = ?, reset_expires = ?, updated_at = ? WHERE id = ?",
        (token_hash, time.time() + RESET_TTL, time.time(), user["id"]),
    )
    db.commit()
    return {
        "ok": True,
        "found": True,
        "token": raw,
        "user_id": user["id"],
        "username": user["username"],
        "email": user.get("email") or "",
        "role": user["role"],
    }


def complete_password_reset(db: sqlite3.Connection, token: str, new_password: str) -> dict[str, Any]:
    ensure_schema(db)
    if not token or len(new_password or "") < 10:
        return {"ok": False, "error": "invalid"}
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    row = db.execute(
        "SELECT * FROM portal_users WHERE reset_token_hash = ? LIMIT 1",
        (token_hash,),
    ).fetchone()
    if not row:
        return {"ok": False, "error": "invalid_token"}
    user = dict(row)
    if not user.get("reset_expires") or time.time() > float(user["reset_expires"]):
        return {"ok": False, "error": "expired"}
    set_password(db, int(user["id"]), new_password)
    # alle Sessions dieses Users killen
    db.execute("DELETE FROM auth_sessions WHERE user_id = ?", (user["id"],))
    db.commit()
    return {"ok": True, "username": user["username"]}


def totp_provision(db: sqlite3.Connection, user_id: int) -> dict[str, Any]:
    """Legt TOTP-Secret an (noch nicht enforced bis confirm)."""
    try:
        import pyotp
    except ImportError:
        return {"ok": False, "error": "pyotp_missing"}
    user = get_user_by_id(db, user_id)
    if not user:
        return {"ok": False, "error": "user_missing"}
    secret = pyotp.random_base32()
    db.execute(
        "UPDATE portal_users SET totp_secret = ?, totp_enabled = 0, updated_at = ? WHERE id = ?",
        (secret, time.time(), user_id),
    )
    db.commit()
    issuer = os.getenv("TOTP_ISSUER", "Webschmiede")
    uri = pyotp.TOTP(secret).provisioning_uri(name=user["username"], issuer_name=issuer)
    return {"ok": True, "secret": secret, "otpauth_url": uri}


def totp_confirm(db: sqlite3.Connection, user_id: int, code: str) -> dict[str, Any]:
    try:
        import pyotp
    except ImportError:
        return {"ok": False, "error": "pyotp_missing"}
    user = get_user_by_id(db, user_id)
    if not user or not user.get("totp_secret"):
        return {"ok": False, "error": "no_secret"}
    if not pyotp.TOTP(user["totp_secret"]).verify(str(code or "").strip(), valid_window=1):
        return {"ok": False, "error": "bad_code"}
    db.execute(
        "UPDATE portal_users SET totp_enabled = 1, updated_at = ? WHERE id = ?",
        (time.time(), user_id),
    )
    db.commit()
    return {"ok": True}


def totp_verify(user: dict[str, Any], code: str) -> bool:
    if not user or not user.get("totp_enabled") or not user.get("totp_secret"):
        return True  # nicht aktiv → ok
    try:
        import pyotp
    except ImportError:
        return False
    return bool(pyotp.TOTP(user["totp_secret"]).verify(str(code or "").strip(), valid_window=1))


def public_user(user: dict[str, Any] | None) -> dict[str, Any] | None:
    if not user:
        return None
    return {
        "id": user["id"],
        "username": user["username"],
        "email": user.get("email") or "",
        "role": user["role"],
        "kunde_id": user.get("kunde_id"),
        "totp_enabled": bool(user.get("totp_enabled")),
    }
