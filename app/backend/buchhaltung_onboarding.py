"""Buchhaltungs-Onboarding: Tools, Fragen, Angebot, Credentials erst nach AVV.

DSGVO: Keine Klartext-Secrets in Responses. Vault nur mit AVV-Haken.
n8n-Credentials legt Nils nach Export an (kein Auto-Push ohne OK).
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:  # pragma: no cover
    Fernet = None  # type: ignore
    InvalidToken = Exception  # type: ignore

VAULT_DIR = Path(
    os.getenv(
        "BUCHHALTUNG_VAULT_DIR",
        str(Path(__file__).resolve().parent.parent / "vault" / "buchhaltung"),
    )
)

TOOLS = [
    {"id": "lexware", "label": "Lexware / Lexoffice", "kind": "buchhaltung"},
    {"id": "sevdesk", "label": "sevDesk", "kind": "buchhaltung"},
    {"id": "datev_kanzlei", "label": "Steuerberater mit DATEV", "kind": "kanzlei"},
    {"id": "excel", "label": "Excel / Google Sheets", "kind": "sonst"},
    {"id": "portal", "label": "Eigenes Bestell-/Job-Portal", "kind": "portal"},
    {"id": "meta_ads", "label": "Meta/Facebook Ads Rechnungen", "kind": "ads"},
    {"id": "imap", "label": "Eingangsrechnungen per E-Mail", "kind": "mail"},
    {"id": "whatsapp_belege", "label": "Belege oft per WhatsApp", "kind": "beleg"},
    {"id": "crm", "label": "CRM (HubSpot, Pipedrive, eigenes…)", "kind": "crm"},
    {"id": "projektboard", "label": "Projektboard (ClickUp, Monday…)", "kind": "crm"},
]

QUESTIONS = [
    {
        "id": "zeitfresser",
        "text": "Wo verliert ihr jede Woche am meisten Zeit bei Belegen und Zahlen?",
        "type": "text",
        "required": True,
    },
    {
        "id": "wer_tippt",
        "text": "Wer tippt das heute ab (Name/Rolle)?",
        "type": "text",
        "required": True,
    },
    {
        "id": "nie_allein",
        "text": "Was darf die Automation nie allein entscheiden?",
        "type": "text",
        "required": False,
        "placeholder": "z. B. Zahlungen freigeben, Mahnungen",
    },
    {
        "id": "ziel_30",
        "text": "Welcher eine Prozess soll in 30 Tagen spürbar besser sein?",
        "type": "text",
        "required": True,
    },
    {
        "id": "steuerberater_mail",
        "text": "E-Mail des Steuerberaters / der Kanzlei (für Monatspaket)",
        "type": "email",
        "required": False,
    },
    {
        "id": "standorte",
        "text": "Wie viele Standorte / Firmenmarken?",
        "type": "choice",
        "required": True,
        "choices": ["1", "2", "3+"],
    },
    {
        "id": "freigabe",
        "text": "Wer gibt bei euch frei, und wie schnell?",
        "type": "text",
        "required": True,
    },
    {
        "id": "wuensche",
        "text": "Was ist euch besonders wichtig? Sonderwünsche, Grenzen, Ideen?",
        "type": "text",
        "required": False,
        "placeholder": "Frei schreiben. Was wir wissen sollen, bevor wir bauen.",
    },
]

PACKAGES = {
    "beleg": {
        "tier": "beleg",
        "name": "Beleg-Pipeline",
        "setup_eur": 1200,
        "monthly_eur": 248,
        "tagline": "Vom Foto zur sortierten Monatsmappe",
    },
    "sync": {
        "tier": "sync",
        "name": "Finanz-Sync",
        "setup_eur": 3200,
        "monthly_eur": 398,
        "tagline": "Portal, CRM & Buchhaltung reden miteinander",
    },
    "silo": {
        "tier": "silo",
        "name": "System-Brücke",
        "setup_eur": 5990,
        "monthly_eur": 698,
        "tagline": "Schluss mit der Datensilo-Hölle",
    },
}

CREDENTIAL_FIELDS = [
    {"id": "bookkeeper_email", "label": "Steuerberater E-Mail", "secret": False, "type": "email"},
    {"id": "belege_inbox", "label": "Wunsch: belege@… Adresse / vorhandenes Postfach", "secret": False, "type": "text"},
    {"id": "imap_host", "label": "Mail-Server (IMAP Host)", "secret": False, "type": "text"},
    {"id": "imap_user", "label": "Mail-Benutzer", "secret": False, "type": "text"},
    {
        "id": "imap_app_password",
        "label": "App-Passwort (kein normales Login-Passwort)",
        "secret": True,
        "type": "password",
        "hint": "Bei Google/Microsoft: App-Passwort erzeugen. Niemals das Hauptpasswort.",
    },
    {"id": "lexware_api_key", "label": "Lexware / Lexoffice API-Key", "secret": True, "type": "password"},
    {"id": "sevdesk_api_key", "label": "sevDesk API-Key", "secret": True, "type": "password"},
    {"id": "meta_invoice_note", "label": "Hinweis Meta-Rechnungen (Analyst / Weiterleitung)", "secret": False, "type": "text"},
    {"id": "notes", "label": "Sonstiges für uns", "secret": False, "type": "text"},
]

AVV_TEXT = (
    "Ich bestätige, dass Webschmiede (Christian Kummetat) die hier hinterlegten "
    "Zugangsdaten ausschließlich zur Einrichtung und zum Betrieb der vereinbarten "
    "Automationen (n8n auf unseren Servern in der EU) nutzen darf. "
    "Es gilt der Auftragsverarbeitungsvertrag (AVV). "
    "Keine Weitergabe an Dritte außer notwendiger Subunternehmer (Hosting). "
    "Zugänge können jederzeit widerrufen und gelöscht werden."
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_tables(db: sqlite3.Connection) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS buchhaltung_onboarding (
            id TEXT PRIMARY KEY,
            access_token TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            firma TEXT,
            kontakt TEXT,
            email TEXT,
            tools_json TEXT,
            answers_json TEXT,
            recommended_tier TEXT,
            avv_accepted INTEGER DEFAULT 0,
            avv_at TEXT,
            credentials_set INTEGER DEFAULT 0,
            status TEXT DEFAULT 'draft',
            offer_json TEXT,
            meta_json TEXT
        )
        """
    )
    db.commit()
    VAULT_DIR.mkdir(parents=True, exist_ok=True)


def schema() -> dict[str, Any]:
    return {
        "ok": True,
        "tools": TOOLS,
        "questions": QUESTIONS,
        "packages": list(PACKAGES.values()),
        "credential_fields": CREDENTIAL_FIELDS,
        "avv_text": AVV_TEXT,
        "steps": [
            "firma",
            "tools",
            "fragen",
            "angebot",
            "avv",
            "zugaenge",
            "fertig",
        ],
        "dsgvo": {
            "vault": "AES (Fernet), Datei außerhalb Webroot",
            "no_plaintext_api": True,
            "app_password_preferred": True,
            "avv_required_before_credentials": True,
            "customer_mails_need_owner_freigabe": True,
            "wuensche_stored_in_session_not_public_api_secrets": True,
        },
    }


def recommend_tier(tools: list[str], answers: dict[str, Any] | None = None) -> dict[str, Any]:
    t = {x.strip().lower() for x in (tools or [])}
    answers = answers or {}
    score = 0
    reasons: list[str] = []

    if t & {"lexware", "sevdesk"}:
        score += 2
        reasons.append("Buchhaltungs-Software vorhanden → Sync sinnvoll")
    if "portal" in t:
        score += 2
        reasons.append("Eigenes Portal → Anbindung an Monats-Export")
    if t & {"crm", "projektboard"}:
        score += 3
        reasons.append("CRM/Board zusätzlich → System-Brücke prüfen")
    if "imap" in t or "whatsapp_belege" in t:
        score += 1
        reasons.append("Belege per Mail/WhatsApp → Beleg-Pipeline Basis")
    if "meta_ads" in t:
        score += 1
        reasons.append("Meta-Rechnungen → Beleg-Pipeline mit IMAP")
    if "datev_kanzlei" in t and not (t & {"lexware", "sevdesk"}):
        score += 0
        reasons.append("DATEV über Kanzlei → oft reicht Beleg-Pipeline")
    if (answers.get("standorte") or "") in ("2", "3+"):
        score += 2
        reasons.append("Mehrere Standorte → eher Sync/Silo")

    if score >= 6:
        tier = "silo"
    elif score >= 3:
        tier = "sync"
    else:
        tier = "beleg"

    pkg = dict(PACKAGES[tier])
    pkg["reasons"] = reasons or ["Basis: sortierte Monatsmappe für die Kanzlei"]
    pkg["score"] = score
    pkg["note"] = (
        "Empfehlung aus euren Angaben. Christian kann die Stufe im Gespräch anpassen. "
        "Keine Steuerberatung, keine laufende Buchführung."
    )
    return pkg


def _row(r: sqlite3.Row | None) -> dict[str, Any] | None:
    if not r:
        return None
    d = dict(r)
    for key in ("tools_json", "answers_json", "offer_json", "meta_json"):
        raw = d.pop(key, None)
        name = key.replace("_json", "")
        if raw:
            try:
                d[name] = json.loads(raw)
            except Exception:
                d[name] = None
        else:
            d[name] = None if name != "tools" else []
    d["avv_accepted"] = bool(d.get("avv_accepted"))
    d["credentials_set"] = bool(d.get("credentials_set"))
    # access_token nie an Client außer create
    return d


def public_view(row: dict[str, Any], *, include_token: bool = False) -> dict[str, Any]:
    out = {
        "ok": True,
        "id": row.get("id"),
        "firma": row.get("firma"),
        "kontakt": row.get("kontakt"),
        "email": row.get("email"),
        "tools": row.get("tools") or [],
        "answers": row.get("answers") or {},
        "recommended_tier": row.get("recommended_tier"),
        "offer": row.get("offer"),
        "avv_accepted": row.get("avv_accepted"),
        "avv_at": row.get("avv_at"),
        "credentials_set": row.get("credentials_set"),
        "status": row.get("status"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "credential_fields_status": _credential_field_status(row.get("id") or ""),
    }
    if include_token:
        out["access_token"] = row.get("access_token")
        out["link"] = f"/buchhaltung-onboarding.html?id={row.get('id')}&t={row.get('access_token')}"
    return out


def create_session(
    db: sqlite3.Connection,
    *,
    firma: str = "",
    kontakt: str = "",
    email: str = "",
) -> dict[str, Any]:
    ensure_tables(db)
    sid = uuid.uuid4().hex[:12]
    token = secrets.token_urlsafe(24)
    db.execute(
        """
        INSERT INTO buchhaltung_onboarding (id, access_token, firma, kontakt, email, status)
        VALUES (?, ?, ?, ?, ?, 'draft')
        """,
        (sid, token, (firma or "").strip()[:120], (kontakt or "").strip()[:120], (email or "").strip()[:160]),
    )
    db.commit()
    row = get_raw(db, sid)
    assert row
    view = public_view(row, include_token=True)
    view["schema"] = schema()
    return view


def get_raw(db: sqlite3.Connection, session_id: str) -> dict[str, Any] | None:
    ensure_tables(db)
    r = db.execute(
        "SELECT * FROM buchhaltung_onboarding WHERE id = ?",
        ((session_id or "").strip(),),
    ).fetchone()
    return _row(r)


def auth_session(db: sqlite3.Connection, session_id: str, token: str) -> dict[str, Any] | None:
    row = get_raw(db, session_id)
    if not row:
        return None
    if not secrets.compare_digest(str(row.get("access_token") or ""), str(token or "")):
        return None
    return row


def save_firma(
    db: sqlite3.Connection,
    session_id: str,
    *,
    firma: str,
    kontakt: str = "",
    email: str = "",
) -> dict[str, Any]:
    db.execute(
        """
        UPDATE buchhaltung_onboarding
        SET firma=?, kontakt=?, email=?, updated_at=datetime('now'), status='firma'
        WHERE id=?
        """,
        ((firma or "").strip()[:120], (kontakt or "").strip()[:120], (email or "").strip()[:160], session_id),
    )
    db.commit()
    view = public_view(get_raw(db, session_id) or {})
    _ping_sales(db, session_id, "discovery_started")
    return view


def save_tools_and_answers(
    db: sqlite3.Connection,
    session_id: str,
    *,
    tools: list[str],
    answers: dict[str, Any],
) -> dict[str, Any]:
    clean_tools = [t for t in tools if any(x["id"] == t for x in TOOLS)]
    offer = recommend_tier(clean_tools, answers)
    db.execute(
        """
        UPDATE buchhaltung_onboarding
        SET tools_json=?, answers_json=?, recommended_tier=?, offer_json=?,
            updated_at=datetime('now'), status='angebot'
        WHERE id=?
        """,
        (
            json.dumps(clean_tools, ensure_ascii=False),
            json.dumps(answers or {}, ensure_ascii=False),
            offer["tier"],
            json.dumps(offer, ensure_ascii=False),
            session_id,
        ),
    )
    db.commit()
    view = public_view(get_raw(db, session_id) or {})
    _ping_sales(db, session_id, "discovery_answers", extra=f"Tier-Empfehlung: {offer.get('name')}")
    return view


def _ping_sales(db: sqlite3.Connection, discovery_id: str, stage: str, extra: str = "") -> None:
    try:
        import sales_pipeline as sales
        import sales_companion as companion

        r = db.execute(
            "SELECT * FROM sales_deals WHERE discovery_id = ? ORDER BY datetime(created_at) DESC LIMIT 1",
            (discovery_id,),
        ).fetchone()
        deal = sales._row(r) if r else None  # noqa: SLF001
        if not deal:
            return
        companion.ping_owner(deal, stage=stage, db=db, extra=extra)
    except Exception:
        pass


def accept_avv(db: sqlite3.Connection, session_id: str, *, name: str = "") -> dict[str, Any]:
    meta = {"avv_name": (name or "").strip()[:120]}
    db.execute(
        """
        UPDATE buchhaltung_onboarding
        SET avv_accepted=1, avv_at=?, updated_at=datetime('now'), status='avv',
            meta_json=?
        WHERE id=?
        """,
        (_now(), json.dumps(meta, ensure_ascii=False), session_id),
    )
    db.commit()
    return public_view(get_raw(db, session_id) or {})


def _vault_key() -> bytes:
    raw = (
        os.getenv("BUCHHALTUNG_VAULT_KEY")
        or os.getenv("AGENCY_ADMIN_PASSWORD")
        or os.getenv("CRON_SECRET")
        or "webschmiede-dev-only"
    ).encode("utf-8")
    digest = hashlib.sha256(raw).digest()
    return base64.urlsafe_b64encode(digest)


def _fernet() -> Any:
    if Fernet is None:
        raise RuntimeError("cryptography fehlt – pip install cryptography")
    return Fernet(_vault_key())


def _vault_path(session_id: str) -> Path:
    safe = "".join(c for c in session_id if c.isalnum())[:32]
    return VAULT_DIR / f"{safe}.enc"


def _credential_field_status(session_id: str) -> dict[str, bool]:
    path = _vault_path(session_id)
    if not path.is_file():
        return {f["id"]: False for f in CREDENTIAL_FIELDS}
    try:
        data = json.loads(_fernet().decrypt(path.read_bytes()).decode("utf-8"))
        return {f["id"]: bool(data.get(f["id"])) for f in CREDENTIAL_FIELDS}
    except Exception:
        return {f["id"]: False for f in CREDENTIAL_FIELDS}


def save_credentials(
    db: sqlite3.Connection,
    session_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    row = get_raw(db, session_id)
    if not row:
        return {"ok": False, "error": "Session unbekannt"}
    if not row.get("avv_accepted"):
        return {
            "ok": False,
            "error": "AVV zuerst bestätigen. Ohne AVV speichern wir keine Zugänge.",
            "need_avv": True,
        }
    clean: dict[str, str] = {}
    for field in CREDENTIAL_FIELDS:
        val = payload.get(field["id"])
        if val is None or str(val).strip() == "":
            continue
        clean[field["id"]] = str(val).strip()[:2000]
    if not clean:
        return {"ok": False, "error": "Keine Felder ausgefüllt"}

    # Merge with existing vault
    path = _vault_path(session_id)
    existing: dict[str, str] = {}
    if path.is_file():
        try:
            existing = json.loads(_fernet().decrypt(path.read_bytes()).decode("utf-8"))
        except Exception:
            existing = {}
    existing.update(clean)
    existing["_updated"] = _now()
    existing["_session"] = session_id
    blob = _fernet().encrypt(json.dumps(existing, ensure_ascii=False).encode("utf-8"))
    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    path.write_bytes(blob)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass

    db.execute(
        """
        UPDATE buchhaltung_onboarding
        SET credentials_set=1, updated_at=datetime('now'), status='credentials'
        WHERE id=?
        """,
        (session_id,),
    )
    db.commit()
    view = public_view(get_raw(db, session_id) or {})
    view["ok"] = True
    view["saved_fields"] = list(clean.keys())
    view["hint"] = "Gespeichert verschlüsselt. Werte werden nicht zurückgegeben."
    return view


def complete(db: sqlite3.Connection, session_id: str) -> dict[str, Any]:
    db.execute(
        """
        UPDATE buchhaltung_onboarding
        SET status='done', updated_at=datetime('now')
        WHERE id=?
        """,
        (session_id,),
    )
    db.commit()
    view = public_view(get_raw(db, session_id) or {})
    view["ok"] = True
    view["next"] = (
        "Christian bekommt die Session. n8n-Credentials legt Nils manuell an "
        "(Export nur mit Agency-Auth)."
    )
    # Sales-Pipeline: Research + Pain-Angebot an Kunden
    try:
        import sales_pipeline as sales

        sales_result = sales.on_discovery_complete(db, session_id)
        view["sales"] = {
            "ok": sales_result.get("ok"),
            "deal_id": sales_result.get("id"),
            "status": sales_result.get("status"),
            "mail": (sales_result.get("mail") or {}).get("ok"),
        }
    except Exception as e:
        view["sales"] = {"ok": False, "error": str(e)[:160]}
    return view


def list_sessions(db: sqlite3.Connection, limit: int = 50) -> dict[str, Any]:
    ensure_tables(db)
    rows = db.execute(
        """
        SELECT id, created_at, updated_at, firma, kontakt, email, recommended_tier,
               avv_accepted, credentials_set, status
        FROM buchhaltung_onboarding
        ORDER BY datetime(updated_at) DESC
        LIMIT ?
        """,
        (max(1, min(limit, 200)),),
    ).fetchall()
    items = []
    for r in rows:
        d = dict(r)
        d["avv_accepted"] = bool(d.get("avv_accepted"))
        d["credentials_set"] = bool(d.get("credentials_set"))
        items.append(d)
    return {"ok": True, "count": len(items), "sessions": items}


def export_credentials_agency(db: sqlite3.Connection, session_id: str) -> dict[str, Any]:
    """Nur Agency: Klartext für n8n-Einrichtung. Wird geloggt."""
    row = get_raw(db, session_id)
    if not row:
        return {"ok": False, "error": "Session unbekannt"}
    if not row.get("avv_accepted"):
        return {"ok": False, "error": "AVV fehlt"}
    path = _vault_path(session_id)
    if not path.is_file():
        return {"ok": False, "error": "Kein Vault"}
    try:
        data = json.loads(_fernet().decrypt(path.read_bytes()).decode("utf-8"))
    except InvalidToken:
        return {"ok": False, "error": "Vault nicht lesbar (falscher Key?)"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}
    # Audit
    audit = VAULT_DIR / "audit.log"
    try:
        with audit.open("a", encoding="utf-8") as f:
            f.write(f"{_now()} export session={session_id} firma={row.get('firma')}\n")
    except OSError:
        pass
    return {
        "ok": True,
        "session_id": session_id,
        "firma": row.get("firma"),
        "tier": row.get("recommended_tier"),
        "offer": row.get("offer"),
        "credentials": data,
        "warning": "Nur einmalig für n8n nutzen. Nicht in Chat/Git kopieren.",
    }


def notify_owner(session: dict[str, Any]) -> dict[str, Any]:
    try:
        from agency_mail import send_html_email, _read_secrets

        sec = _read_secrets()
        to = (os.getenv("AGENCY_OWNER_EMAIL") or sec.get("AGENCY_OWNER_EMAIL") or sec.get("AGENCY_SMTP_USER") or "").strip()
        if not to:
            return {"ok": False, "error": "AGENCY_OWNER_EMAIL fehlt"}
        offer = session.get("offer") or {}
        subject = f"[Buchhaltung-Onboarding] {session.get('firma') or session.get('id')} · {offer.get('name') or '?'}"
        text = (
            f"Firma: {session.get('firma')}\n"
            f"Kontakt: {session.get('kontakt')} {session.get('email')}\n"
            f"Stufe: {offer.get('name')} ({offer.get('tier')})\n"
            f"Setup ~{offer.get('setup_eur')} € · Monat ~{offer.get('monthly_eur')} €\n"
            f"AVV: {session.get('avv_accepted')} · Credentials: {session.get('credentials_set')}\n"
            f"Session: {session.get('id')}\n"
            f"Export: POST /api/buchhaltung/onboarding/{session.get('id')}/export (Agency-Auth)\n"
        )
        html = f"<pre style='font-family:system-ui'>{text}</pre>"
        send_html_email(to=to, subject=subject, html=html, text=text)
        return {"ok": True, "to": to}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}
