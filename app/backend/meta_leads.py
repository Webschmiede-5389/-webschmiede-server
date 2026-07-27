# -*- coding: utf-8 -*-
"""Meta Lead Ads: Webhook → Graph API → SQLite → Dashboard → E-Mail.

Parallel zu GHL. Keine Tokens in DB/Logs – nur env-Variablennamen.
"""
from __future__ import annotations

import hashlib
import hmac
import html
import json
import logging
import os
import re
import smtplib
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Callable

import requests

log = logging.getLogger("meta_leads")

POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="meta-leads")

STATUSES = ("neu", "kontaktiert", "qualifiziert", "termin", "gewonnen", "verloren")
TOKEN_KEYS = ("access_token", "appsecret_proof", "token", "password", "secret", "authorization")

_GetDb = Callable[[], sqlite3.Connection]


def graph_api_version() -> str:
    return (os.getenv("META_GRAPH_API_VERSION") or "v21.0").strip() or "v21.0"


def verify_token_configured() -> str:
    return (os.getenv("META_LEAD_VERIFY_TOKEN") or "").strip()


def app_secret() -> str:
    return (
        os.getenv("META_LEAD_APP_SECRET")
        or os.getenv("META_APP_SECRET")
        or os.getenv("FACEBOOK_APP_SECRET")
        or ""
    ).strip()


def insecure_no_secret_allowed() -> bool:
    return os.getenv("META_LEAD_WEBHOOK_INSECURE_NO_SECRET", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def max_retries() -> int:
    try:
        return max(1, int(os.getenv("META_LEAD_MAX_RETRIES") or "3"))
    except ValueError:
        return 3


def retry_delay_sec() -> int:
    try:
        return max(10, int(os.getenv("META_LEAD_RETRY_DELAY_SEC") or "60"))
    except ValueError:
        return 60


def verify_signature(payload: bytes, signature_header: str | None) -> bool:
    """X-Hub-Signature-256. Fail-closed ohne Secret (außer Dev-Flag)."""
    secret = app_secret()
    if not secret:
        return insecure_no_secret_allowed()
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature_header[7:], expected)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _strip_secrets(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if any(t in str(k).lower() for t in TOKEN_KEYS):
                out[k] = "[redacted]"
            else:
                out[k] = _strip_secrets(v)
        return out
    if isinstance(obj, list):
        return [_strip_secrets(x) for x in obj]
    return obj


def ensure_tables(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS meta_tenant_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL UNIQUE,
            page_id TEXT NOT NULL,
            form_ids TEXT NOT NULL DEFAULT '[]',
            notify_email TEXT,
            graph_api_version TEXT DEFAULT 'v21.0',
            access_token_env TEXT NOT NULL,
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS meta_leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL,
            meta_lead_id TEXT NOT NULL UNIQUE,
            form_id TEXT,
            page_id TEXT,
            ad_id TEXT,
            ad_name TEXT,
            adset_id TEXT,
            campaign_id TEXT,
            is_test INTEGER DEFAULT 0,
            created_time TEXT,
            full_name TEXT,
            email TEXT,
            phone TEXT,
            custom_fields TEXT DEFAULT '{}',
            status TEXT DEFAULT 'neu',
            notes TEXT,
            assignee TEXT,
            notify_status TEXT DEFAULT 'pending',
            notify_error TEXT,
            import_status TEXT DEFAULT 'pending',
            import_error TEXT,
            retry_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE UNIQUE INDEX IF NOT EXISTS uidx_meta_lead_id ON meta_leads(meta_lead_id);
        CREATE INDEX IF NOT EXISTS idx_meta_leads_tenant ON meta_leads(tenant_id);
        CREATE INDEX IF NOT EXISTS idx_meta_leads_status ON meta_leads(status);
        CREATE TABLE IF NOT EXISTS meta_lead_raw (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER REFERENCES meta_leads(id),
            event_type TEXT,
            payload_json TEXT NOT NULL,
            received_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS meta_lead_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL REFERENCES meta_leads(id),
            tenant_id TEXT NOT NULL,
            field TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            changed_by TEXT,
            changed_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS meta_lead_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL,
            meta_lead_id TEXT NOT NULL,
            job_type TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            retry_count INTEGER DEFAULT 0,
            max_retries INTEGER DEFAULT 3,
            next_retry_at TEXT,
            error_detail TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_meta_jobs_status ON meta_lead_jobs(status);
        """
    )
    db.commit()


def get_config_by_page(db: sqlite3.Connection, page_id: str) -> dict | None:
    ensure_tables(db)
    row = db.execute(
        "SELECT * FROM meta_tenant_configs WHERE page_id=? AND active=1",
        (page_id,),
    ).fetchone()
    return dict(row) if row else None


def get_config_by_tenant(db: sqlite3.Connection, tenant_id: str) -> dict | None:
    ensure_tables(db)
    row = db.execute(
        "SELECT * FROM meta_tenant_configs WHERE tenant_id=? COLLATE NOCASE",
        (tenant_id.upper(),),
    ).fetchone()
    return dict(row) if row else None


def upsert_tenant_config(db: sqlite3.Connection, data: dict) -> dict:
    ensure_tables(db)
    tenant_id = (data.get("tenant_id") or os.getenv("KUNDE_ID") or "").strip().upper()
    page_id = (data.get("page_id") or "").strip()
    access_token_env = (data.get("access_token_env") or "").strip()
    if not tenant_id or not page_id or not access_token_env:
        raise ValueError("tenant_id, page_id und access_token_env sind Pflicht")
    form_ids = data.get("form_ids") or []
    if isinstance(form_ids, str):
        form_ids = json.loads(form_ids or "[]")
    notify_email = (data.get("notify_email") or "").strip() or None
    version = (data.get("graph_api_version") or graph_api_version()).strip()
    active = 1 if data.get("active", True) else 0
    existing = get_config_by_tenant(db, tenant_id)
    if existing:
        db.execute(
            """UPDATE meta_tenant_configs SET
               page_id=?, form_ids=?, notify_email=?, graph_api_version=?,
               access_token_env=?, active=?, updated_at=datetime('now')
               WHERE tenant_id=?""",
            (
                page_id,
                json.dumps(form_ids, ensure_ascii=False),
                notify_email,
                version,
                access_token_env,
                active,
                tenant_id,
            ),
        )
    else:
        db.execute(
            """INSERT INTO meta_tenant_configs
               (tenant_id, page_id, form_ids, notify_email, graph_api_version,
                access_token_env, active)
               VALUES (?,?,?,?,?,?,?)""",
            (
                tenant_id,
                page_id,
                json.dumps(form_ids, ensure_ascii=False),
                notify_email,
                version,
                access_token_env,
                active,
            ),
        )
    db.commit()
    cfg = get_config_by_tenant(db, tenant_id)
    assert cfg
    return cfg


def resolve_access_token(cfg: dict) -> str:
    env_name = (cfg.get("access_token_env") or "").strip()
    if not env_name or not re.match(r"^[A-Z][A-Z0-9_]*$", env_name):
        raise ValueError("access_token_env ungültig")
    token = (os.getenv(env_name) or "").strip()
    if not token:
        raise ValueError(f"Env {env_name} ist leer oder nicht gesetzt")
    return token


def parse_leadgen_events(payload: dict) -> list[dict[str, Any]]:
    """Extrahiert leadgen-Änderungen aus Meta Webhook-Payload."""
    out: list[dict[str, Any]] = []
    for entry in payload.get("entry") or []:
        page_id = str(entry.get("id") or "").strip()
        for change in entry.get("changes") or []:
            if (change.get("field") or "") != "leadgen":
                continue
            val = change.get("value") or {}
            lead_id = str(val.get("leadgen_id") or "").strip()
            if not lead_id:
                continue
            out.append({
                "page_id": page_id or str(val.get("page_id") or "").strip(),
                "meta_lead_id": lead_id,
                "form_id": str(val.get("form_id") or "").strip() or None,
                "ad_id": str(val.get("ad_id") or "").strip() or None,
                "adgroup_id": str(val.get("adgroup_id") or "").strip() or None,
                "created_time": str(val.get("created_time") or "").strip() or None,
                "is_test": bool(val.get("is_test") or val.get("test_event")),
            })
    return out


def enqueue_fetch_job(
    db: sqlite3.Connection,
    *,
    tenant_id: str,
    meta_lead_id: str,
) -> int | None:
    ensure_tables(db)
    existing = db.execute(
        """SELECT id, status FROM meta_lead_jobs
           WHERE meta_lead_id=? AND job_type='fetch_lead'
           AND status IN ('pending','running','retrying','done')
           ORDER BY id DESC LIMIT 1""",
        (meta_lead_id,),
    ).fetchone()
    if existing and existing["status"] == "done":
        return None
    if existing and existing["status"] in ("pending", "running", "retrying"):
        return int(existing["id"])
    cur = db.execute(
        """INSERT INTO meta_lead_jobs
           (tenant_id, meta_lead_id, job_type, status, max_retries)
           VALUES (?,?,?,?,?)""",
        (tenant_id, meta_lead_id, "fetch_lead", "pending", max_retries()),
    )
    db.commit()
    return int(cur.lastrowid)


def claim_or_skip_lead_stub(
    db: sqlite3.Connection,
    *,
    tenant_id: str,
    event: dict,
) -> tuple[bool, int | None]:
    """Legt Stub-Lead an. Returns (is_new, lead_row_id). False = Duplikat."""
    ensure_tables(db)
    meta_lead_id = event["meta_lead_id"]
    row = db.execute(
        "SELECT id FROM meta_leads WHERE meta_lead_id=?",
        (meta_lead_id,),
    ).fetchone()
    if row:
        return False, int(row["id"])
    try:
        cur = db.execute(
            """INSERT INTO meta_leads
               (tenant_id, meta_lead_id, form_id, page_id, ad_id, adset_id,
                created_time, is_test, import_status)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                tenant_id,
                meta_lead_id,
                event.get("form_id"),
                event.get("page_id"),
                event.get("ad_id"),
                event.get("adgroup_id"),
                event.get("created_time"),
                1 if event.get("is_test") else 0,
                "pending",
            ),
        )
        db.commit()
        lead_id = int(cur.lastrowid)
        db.execute(
            """INSERT INTO meta_lead_raw (lead_id, event_type, payload_json)
               VALUES (?,?,?)""",
            (
                lead_id,
                "webhook",
                json.dumps(_strip_secrets(event), ensure_ascii=False),
            ),
        )
        db.commit()
        return True, lead_id
    except sqlite3.IntegrityError:
        row = db.execute(
            "SELECT id FROM meta_leads WHERE meta_lead_id=?",
            (meta_lead_id,),
        ).fetchone()
        return False, int(row["id"]) if row else None


def handle_webhook_post(
    db: sqlite3.Connection,
    payload: dict,
    *,
    get_db: _GetDb | None = None,
) -> dict:
    """Verarbeitet POST sofort: Stubs + Jobs, Worker asynchron."""
    ensure_tables(db)
    events = parse_leadgen_events(payload)
    accepted = 0
    duplicates = 0
    unknown_pages = 0
    for ev in events:
        cfg = get_config_by_page(db, ev["page_id"])
        if not cfg:
            unknown_pages += 1
            log.warning("meta_leads: keine Config für page_id=%s", ev["page_id"])
            continue
        is_new, _lead_id = claim_or_skip_lead_stub(
            db, tenant_id=cfg["tenant_id"], event=ev
        )
        if not is_new:
            duplicates += 1
            continue
        job_id = enqueue_fetch_job(
            db, tenant_id=cfg["tenant_id"], meta_lead_id=ev["meta_lead_id"]
        )
        accepted += 1
        if job_id is not None:
            _submit_job(job_id, get_db=get_db)
    return {
        "ok": True,
        "events": len(events),
        "accepted": accepted,
        "duplicates": duplicates,
        "unknown_pages": unknown_pages,
    }


def _submit_job(job_id: int, *, get_db: _GetDb | None = None) -> None:
    def _worker() -> None:
        try:
            if get_db:
                db = get_db()
            else:
                path = os.getenv("DB_PATH") or os.path.join(
                    os.path.dirname(__file__), "orders.db"
                )
                db = sqlite3.connect(path, timeout=30)
                db.row_factory = sqlite3.Row
            try:
                process_job(db, job_id)
            finally:
                db.close()
        except Exception:
            log.exception("meta_leads worker job_id=%s", job_id)

    POOL.submit(_worker)


def process_job(db: sqlite3.Connection, job_id: int) -> None:
    ensure_tables(db)
    row = db.execute("SELECT * FROM meta_lead_jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        return
    job = dict(row)
    if job["status"] == "done":
        return
    db.execute(
        """UPDATE meta_lead_jobs SET status='running', updated_at=datetime('now')
           WHERE id=?""",
        (job_id,),
    )
    db.commit()
    try:
        if job["job_type"] == "fetch_lead":
            _fetch_and_store(db, job)
        elif job["job_type"] == "send_email":
            _send_notify_for_lead(db, job["meta_lead_id"], job["tenant_id"])
        else:
            raise ValueError(f"Unbekannter job_type: {job['job_type']}")
        db.execute(
            """UPDATE meta_lead_jobs SET status='done', error_detail=NULL,
               updated_at=datetime('now') WHERE id=?""",
            (job_id,),
        )
        db.commit()
    except Exception as e:
        retries = int(job.get("retry_count") or 0) + 1
        max_r = int(job.get("max_retries") or max_retries())
        detail = str(e)[:500]
        if retries >= max_r:
            status = "failed"
            next_at = None
        else:
            status = "retrying"
            next_at = datetime.fromtimestamp(
                time.time() + retry_delay_sec(), tz=timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
        db.execute(
            """UPDATE meta_lead_jobs SET status=?, retry_count=?, next_retry_at=?,
               error_detail=?, updated_at=datetime('now') WHERE id=?""",
            (status, retries, next_at, detail, job_id),
        )
        db.execute(
            """UPDATE meta_leads SET import_status=?, import_error=?,
               retry_count=?, updated_at=datetime('now')
               WHERE meta_lead_id=?""",
            (
                "error" if status == "failed" else "pending",
                detail,
                retries,
                job["meta_lead_id"],
            ),
        )
        db.commit()
        log.warning("meta_leads job %s %s: %s", job_id, status, detail)


def _fetch_and_store(db: sqlite3.Connection, job: dict) -> None:
    cfg = get_config_by_tenant(db, job["tenant_id"])
    if not cfg:
        raise ValueError("Tenant-Config fehlt")
    token = resolve_access_token(cfg)
    version = (cfg.get("graph_api_version") or graph_api_version()).strip()
    lead_id = job["meta_lead_id"]
    url = f"https://graph.facebook.com/{version}/{lead_id}"
    # Kein Token in Logs
    r = requests.get(
        url,
        params={
            "access_token": token,
            "fields": "id,created_time,ad_id,ad_name,adset_id,campaign_id,form_id,field_data,is_organic",
        },
        timeout=20,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"Graph API HTTP {r.status_code}")
    data = r.json()
    safe = _strip_secrets(data)
    parsed = _parse_field_data(data.get("field_data") or [])
    db.execute(
        """UPDATE meta_leads SET
           form_id=COALESCE(?, form_id),
           ad_id=COALESCE(?, ad_id),
           ad_name=COALESCE(?, ad_name),
           adset_id=COALESCE(?, adset_id),
           campaign_id=COALESCE(?, campaign_id),
           created_time=COALESCE(?, created_time),
           full_name=?, email=?, phone=?,
           custom_fields=?,
           import_status='done', import_error=NULL,
           updated_at=datetime('now')
           WHERE meta_lead_id=?""",
        (
            data.get("form_id"),
            data.get("ad_id"),
            data.get("ad_name"),
            data.get("adset_id"),
            data.get("campaign_id"),
            data.get("created_time"),
            parsed.get("full_name"),
            parsed.get("email"),
            parsed.get("phone"),
            json.dumps(parsed.get("custom") or {}, ensure_ascii=False),
            lead_id,
        ),
    )
    lead_row = db.execute(
        "SELECT id FROM meta_leads WHERE meta_lead_id=?",
        (lead_id,),
    ).fetchone()
    if lead_row:
        db.execute(
            """INSERT INTO meta_lead_raw (lead_id, event_type, payload_json)
               VALUES (?,?,?)""",
            (int(lead_row["id"]), "graph_api", json.dumps(safe, ensure_ascii=False)),
        )
    db.commit()
    _send_notify_for_lead(db, lead_id, job["tenant_id"])


def _parse_field_data(field_data: list) -> dict[str, Any]:
    custom: dict[str, str] = {}
    full_name = email = phone = None
    name_map = {
        "full_name": "full_name",
        "fullname": "full_name",
        "first_name": "first_name",
        "last_name": "last_name",
        "email": "email",
        "phone_number": "phone",
        "phone": "phone",
    }
    first = last = None
    for item in field_data:
        name = str(item.get("name") or "").strip().lower()
        values = item.get("values") or []
        val = str(values[0]).strip() if values else ""
        if not name:
            continue
        key = name_map.get(name)
        if key == "full_name":
            full_name = val
        elif key == "first_name":
            first = val
        elif key == "last_name":
            last = val
        elif key == "email":
            email = val
        elif key == "phone":
            phone = val
        else:
            custom[name] = val
    if not full_name and (first or last):
        full_name = " ".join(x for x in (first, last) if x).strip()
    return {"full_name": full_name, "email": email, "phone": phone, "custom": custom}


def _send_notify_for_lead(db: sqlite3.Connection, meta_lead_id: str, tenant_id: str) -> None:
    cfg = get_config_by_tenant(db, tenant_id)
    lead = db.execute(
        "SELECT * FROM meta_leads WHERE meta_lead_id=?",
        (meta_lead_id,),
    ).fetchone()
    if not lead:
        raise ValueError("Lead nicht gefunden")
    lead_d = dict(lead)
    if lead_d.get("notify_status") == "sent":
        return
    to = (cfg or {}).get("notify_email") or ""
    if not to:
        db.execute(
            """UPDATE meta_leads SET notify_status='failed',
               notify_error=?, updated_at=datetime('now') WHERE meta_lead_id=?""",
            ("notify_email fehlt in Tenant-Config", meta_lead_id),
        )
        db.commit()
        return
    try:
        _smtp_notify(to, lead_d, tenant_id)
        db.execute(
            """UPDATE meta_leads SET notify_status='sent', notify_error=NULL,
               updated_at=datetime('now') WHERE meta_lead_id=?""",
            (meta_lead_id,),
        )
        db.commit()
    except Exception as e:
        detail = str(e)[:500]
        db.execute(
            """UPDATE meta_leads SET notify_status='failed', notify_error=?,
               updated_at=datetime('now') WHERE meta_lead_id=?""",
            (detail, meta_lead_id),
        )
        db.commit()
        # Retry-Job für E-Mail
        db.execute(
            """INSERT INTO meta_lead_jobs
               (tenant_id, meta_lead_id, job_type, status, max_retries, next_retry_at)
               VALUES (?,?,?,?,?,?)""",
            (
                tenant_id,
                meta_lead_id,
                "send_email",
                "retrying",
                max_retries(),
                datetime.fromtimestamp(
                    time.time() + retry_delay_sec(), tz=timezone.utc
                ).strftime("%Y-%m-%dT%H:%M:%SZ"),
            ),
        )
        db.commit()
        raise


def _smtp_notify(to: str, lead: dict, tenant_id: str) -> None:
    host = (os.getenv("SMTP_HOST") or os.getenv("AGENCY_SMTP_HOST") or "").strip()
    user = (os.getenv("SMTP_USER") or os.getenv("AGENCY_SMTP_USER") or "").strip()
    password = (os.getenv("SMTP_PASS") or os.getenv("AGENCY_SMTP_PASS") or "").strip()
    from_addr = (
        os.getenv("SMTP_FROM")
        or os.getenv("AGENCY_SMTP_FROM")
        or user
        or ""
    ).strip()
    port = int(os.getenv("SMTP_PORT") or os.getenv("AGENCY_SMTP_PORT") or "587")
    if not host or not user or not password or not from_addr:
        raise RuntimeError("SMTP nicht konfiguriert")
    name = html.escape(lead.get("full_name") or "—")
    email = html.escape(lead.get("email") or "—")
    phone = html.escape(lead.get("phone") or "—")
    test_badge = " [TEST]" if lead.get("is_test") else ""
    subject = f"Neuer Meta-Lead{test_badge}: {lead.get('full_name') or lead.get('meta_lead_id')} ({tenant_id})"
    body = f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;">
      <h2 style="color:#1a1a1a;">Neuer Meta Lead Ad{test_badge}</h2>
      <p><b>Mandant:</b> {html.escape(tenant_id)}</p>
      <p><b>Name:</b> {name}<br>
         <b>E-Mail:</b> {email}<br>
         <b>Telefon:</b> {phone}</p>
      <p><b>Meta Lead ID:</b> {html.escape(str(lead.get('meta_lead_id') or ''))}<br>
         <b>Form:</b> {html.escape(str(lead.get('form_id') or '—'))}<br>
         <b>Ad:</b> {html.escape(str(lead.get('ad_name') or lead.get('ad_id') or '—'))}</p>
      <p style="color:#666;font-size:12px;">Quelle: Meta Lead Ads (eigenes CRM, parallel zu GHL)</p>
    </div>
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to
    msg.attach(MIMEText(body, "html", "utf-8"))
    with smtplib.SMTP(host, port, timeout=30) as s:
        s.starttls()
        s.login(user, password)
        s.sendmail(from_addr, to, msg.as_string())


def list_leads(
    db: sqlite3.Connection,
    *,
    tenant_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[dict]:
    ensure_tables(db)
    q = "SELECT * FROM meta_leads WHERE 1=1"
    params: list[Any] = []
    if tenant_id:
        q += " AND tenant_id=?"
        params.append(tenant_id.upper())
    if status:
        q += " AND status=?"
        params.append(status)
    q += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = [dict(r) for r in db.execute(q, params).fetchall()]
    for r in rows:
        try:
            r["custom_fields"] = json.loads(r.get("custom_fields") or "{}")
        except json.JSONDecodeError:
            r["custom_fields"] = {}
    return rows


def get_lead(db: sqlite3.Connection, lead_id: int) -> dict | None:
    ensure_tables(db)
    row = db.execute("SELECT * FROM meta_leads WHERE id=?", (lead_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        d["custom_fields"] = json.loads(d.get("custom_fields") or "{}")
    except json.JSONDecodeError:
        d["custom_fields"] = {}
    d["audit"] = [
        dict(a)
        for a in db.execute(
            "SELECT * FROM meta_lead_audit WHERE lead_id=? ORDER BY id DESC LIMIT 50",
            (lead_id,),
        ).fetchall()
    ]
    d["raw"] = [
        dict(a)
        for a in db.execute(
            "SELECT id, event_type, received_at FROM meta_lead_raw WHERE lead_id=? ORDER BY id DESC",
            (lead_id,),
        ).fetchall()
    ]
    return d


def update_lead(
    db: sqlite3.Connection,
    lead_id: int,
    data: dict,
    *,
    changed_by: str = "agency",
) -> dict:
    ensure_tables(db)
    lead = get_lead(db, lead_id)
    if not lead:
        raise ValueError("Lead nicht gefunden")
    fields = {
        "status": data.get("status"),
        "notes": data.get("notes"),
        "assignee": data.get("assignee"),
    }
    for field, new_val in fields.items():
        if new_val is None and field not in data:
            continue
        if field == "status" and new_val is not None:
            new_val = str(new_val).lower().strip()
            if new_val not in STATUSES:
                raise ValueError(f"Ungültiger Status: {new_val}")
        if field == "notes" and new_val is not None:
            new_val = str(new_val)[:5000]
        if field == "assignee" and new_val is not None:
            new_val = str(new_val)[:120]
        old = lead.get(field)
        if str(old or "") == str(new_val or ""):
            continue
        db.execute(
            f"UPDATE meta_leads SET {field}=?, updated_at=datetime('now') WHERE id=?",
            (new_val, lead_id),
        )
        db.execute(
            """INSERT INTO meta_lead_audit
               (lead_id, tenant_id, field, old_value, new_value, changed_by)
               VALUES (?,?,?,?,?,?)""",
            (
                lead_id,
                lead["tenant_id"],
                field,
                str(old) if old is not None else None,
                str(new_val) if new_val is not None else None,
                changed_by[:80],
            ),
        )
    db.commit()
    updated = get_lead(db, lead_id)
    assert updated
    return updated


def process_due_retries(db: sqlite3.Connection, *, get_db: _GetDb | None = None) -> dict:
    ensure_tables(db)
    now = _now()
    rows = db.execute(
        """SELECT id FROM meta_lead_jobs
           WHERE status='retrying' AND (next_retry_at IS NULL OR next_retry_at<=?)
           ORDER BY id ASC LIMIT 50""",
        (now,),
    ).fetchall()
    for r in rows:
        _submit_job(int(r["id"]), get_db=get_db)
    return {"ok": True, "queued": len(rows)}


def cron_sync_missing(db: sqlite3.Connection, *, get_db: _GetDb | None = None) -> dict:
    """Täglicher Abgleich: fehlende Leads aus verbundenen Formularen nachladen."""
    ensure_tables(db)
    configs = [
        dict(r)
        for r in db.execute(
            "SELECT * FROM meta_tenant_configs WHERE active=1"
        ).fetchall()
    ]
    imported = 0
    errors: list[str] = []
    for cfg in configs:
        try:
            token = resolve_access_token(cfg)
            version = (cfg.get("graph_api_version") or graph_api_version()).strip()
            form_ids = json.loads(cfg.get("form_ids") or "[]")
            if not form_ids:
                # Fallback: Page-Leadforms auflisten
                pr = requests.get(
                    f"https://graph.facebook.com/{version}/{cfg['page_id']}/leadgen_forms",
                    params={"access_token": token, "fields": "id,name", "limit": 50},
                    timeout=20,
                )
                if pr.status_code >= 400:
                    raise RuntimeError(f"leadgen_forms HTTP {pr.status_code}")
                form_ids = [f["id"] for f in (pr.json().get("data") or []) if f.get("id")]
            for form_id in form_ids:
                url = f"https://graph.facebook.com/{version}/{form_id}/leads"
                lr = requests.get(
                    url,
                    params={"access_token": token, "fields": "id,created_time", "limit": 50},
                    timeout=30,
                )
                if lr.status_code >= 400:
                    raise RuntimeError(f"form leads HTTP {lr.status_code} form={form_id}")
                for item in lr.json().get("data") or []:
                    mid = str(item.get("id") or "").strip()
                    if not mid:
                        continue
                    exists = db.execute(
                        "SELECT id FROM meta_leads WHERE meta_lead_id=?",
                        (mid,),
                    ).fetchone()
                    if exists:
                        continue
                    ev = {
                        "meta_lead_id": mid,
                        "form_id": str(form_id),
                        "page_id": cfg["page_id"],
                        "created_time": item.get("created_time"),
                        "is_test": False,
                    }
                    is_new, _ = claim_or_skip_lead_stub(
                        db, tenant_id=cfg["tenant_id"], event=ev
                    )
                    if not is_new:
                        continue
                    job_id = enqueue_fetch_job(
                        db, tenant_id=cfg["tenant_id"], meta_lead_id=mid
                    )
                    imported += 1
                    if job_id:
                        _submit_job(job_id, get_db=get_db)
        except Exception as e:
            errors.append(f"{cfg.get('tenant_id')}: {str(e)[:120]}")
            log.warning("meta_leads cron_sync: %s", e)
    retries = process_due_retries(db, get_db=get_db)
    return {"ok": True, "imported": imported, "errors": errors, "retries": retries}


def render_dashboard_html(leads: list[dict], *, tenant_filter: str = "") -> str:
    rows = []
    for lead in leads:
        badge = ""
        if lead.get("is_test"):
            badge = ' <span style="background:#fef3c7;color:#92400e;padding:2px 6px;border-radius:4px;font-size:11px;">TEST</span>'
        err = ""
        if lead.get("import_status") == "error" or lead.get("notify_status") == "failed":
            err = f'<div style="color:#b91c1c;font-size:12px;">{html.escape((lead.get("import_error") or lead.get("notify_error") or "")[:80])}</div>'
        rows.append(
            f"""<tr>
            <td><a href="/agency/meta-leads/{lead['id']}">{lead['id']}</a>{badge}</td>
            <td>{html.escape(lead.get('tenant_id') or '')}</td>
            <td>{html.escape(lead.get('full_name') or '—')}</td>
            <td>{html.escape(lead.get('email') or '—')}<br><span style="color:#666">{html.escape(lead.get('phone') or '')}</span></td>
            <td>{html.escape(lead.get('status') or '')}</td>
            <td>{html.escape(lead.get('import_status') or '')} / {html.escape(lead.get('notify_status') or '')}{err}</td>
            <td style="font-size:12px;color:#666">{html.escape((lead.get('created_at') or '')[:19])}</td>
            </tr>"""
        )
    body = "\n".join(rows) or '<tr><td colspan="7">Keine Leads</td></tr>'
    return f"""<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8"><title>Meta Leads</title>
<style>
body{{font-family:system-ui,sans-serif;margin:24px;background:#f8fafc;color:#0f172a}}
table{{border-collapse:collapse;width:100%;background:#fff;border-radius:8px;overflow:hidden}}
th,td{{padding:10px 12px;border-bottom:1px solid #e2e8f0;text-align:left;vertical-align:top}}
th{{background:#0f172a;color:#fff;font-size:13px}}
a{{color:#1d4ed8}}
.filters{{margin-bottom:16px}}
</style></head><body>
<h1>Meta Lead Ads</h1>
<p>Parallel zu GHL · eigene Erfassung</p>
<div class="filters">
  <form method="get" action="/agency/meta-leads">
    <input name="tenant_id" placeholder="Tenant (z.B. DHK)" value="{html.escape(tenant_filter)}">
    <select name="status">
      <option value="">Alle Status</option>
      {"".join(f'<option value="{s}">{s}</option>' for s in STATUSES)}
    </select>
    <button type="submit">Filtern</button>
  </form>
</div>
<table>
<thead><tr><th>ID</th><th>Tenant</th><th>Name</th><th>Kontakt</th><th>Status</th><th>Import/Mail</th><th>Erstellt</th></tr></thead>
<tbody>{body}</tbody>
</table>
</body></html>"""


def render_lead_detail_html(lead: dict) -> str:
    custom = lead.get("custom_fields") or {}
    custom_rows = "".join(
        f"<tr><td>{html.escape(str(k))}</td><td>{html.escape(str(v))}</td></tr>"
        for k, v in custom.items()
    ) or "<tr><td colspan='2'>—</td></tr>"
    audit_rows = "".join(
        f"<tr><td>{html.escape(a.get('field') or '')}</td>"
        f"<td>{html.escape(str(a.get('old_value') or ''))}</td>"
        f"<td>{html.escape(str(a.get('new_value') or ''))}</td>"
        f"<td>{html.escape(a.get('changed_by') or '')}</td>"
        f"<td>{html.escape((a.get('changed_at') or '')[:19])}</td></tr>"
        for a in (lead.get("audit") or [])
    ) or "<tr><td colspan='5'>—</td></tr>"
    status_opts = "".join(
        f'<option value="{s}"{" selected" if lead.get("status")==s else ""}>{s}</option>'
        for s in STATUSES
    )
    return f"""<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8"><title>Lead #{lead['id']}</title>
<style>
body{{font-family:system-ui,sans-serif;margin:24px;background:#f8fafc;color:#0f172a;max-width:800px}}
.card{{background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:20px;margin-bottom:16px}}
label{{display:block;margin-top:12px;font-size:13px;color:#475569}}
input,select,textarea{{width:100%;padding:8px;margin-top:4px;box-sizing:border-box}}
button{{margin-top:12px;padding:10px 16px;background:#0f172a;color:#fff;border:0;border-radius:6px}}
table{{width:100%;border-collapse:collapse}} th,td{{padding:6px;border-bottom:1px solid #e2e8f0;text-align:left;font-size:13px}}
a{{color:#1d4ed8}}
</style></head><body>
<p><a href="/agency/meta-leads">← Zurück</a></p>
<div class="card">
  <h1>Lead #{lead['id']} {"[TEST]" if lead.get("is_test") else ""}</h1>
  <p><b>{html.escape(lead.get("full_name") or "—")}</b><br>
  {html.escape(lead.get("email") or "")} · {html.escape(lead.get("phone") or "")}</p>
  <p style="font-size:13px;color:#64748b">
    Tenant: {html.escape(lead.get("tenant_id") or "")} ·
    Meta-ID: {html.escape(lead.get("meta_lead_id") or "")}<br>
    Form: {html.escape(str(lead.get("form_id") or "—"))} ·
    Ad: {html.escape(str(lead.get("ad_name") or lead.get("ad_id") or "—"))}<br>
    Import: {html.escape(lead.get("import_status") or "")} ·
    Mail: {html.escape(lead.get("notify_status") or "")}
  </p>
</div>
<div class="card">
  <h2>Bearbeiten</h2>
  <form method="post" action="/agency/meta-leads/{lead['id']}/update">
    <label>Status</label>
    <select name="status">{status_opts}</select>
    <label>Zuständig</label>
    <input name="assignee" value="{html.escape(lead.get("assignee") or "")}">
    <label>Notizen</label>
    <textarea name="notes" rows="5">{html.escape(lead.get("notes") or "")}</textarea>
    <button type="submit">Speichern</button>
  </form>
</div>
<div class="card">
  <h2>Formularfelder</h2>
  <table><thead><tr><th>Feld</th><th>Wert</th></tr></thead><tbody>{custom_rows}</tbody></table>
</div>
<div class="card">
  <h2>Audit</h2>
  <table><thead><tr><th>Feld</th><th>Alt</th><th>Neu</th><th>Von</th><th>Wann</th></tr></thead>
  <tbody>{audit_rows}</tbody></table>
</div>
</body></html>"""
