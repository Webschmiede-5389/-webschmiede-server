"""B2B Kundenportal: Upload -> Kalkulation -> Ergebnis (Gesicht fuer n8n, ohne Budibase)."""
from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any

UPLOAD_ROOT = Path(
    os.getenv(
        "B2B_UPLOAD_DIR",
        str(Path(__file__).resolve().parent.parent / "uploads" / "b2b"),
    )
)

DEFAULT_RETENTION_HOURS = int(os.getenv("B2B_ZERO_RETENTION_HOURS", "24") or "24")


def ensure_tables(db: sqlite3.Connection) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS b2b_jobs (
            id          TEXT PRIMARY KEY,
            created_at  TEXT DEFAULT (datetime('now')),
            updated_at  TEXT DEFAULT (datetime('now')),
            kunde_id    TEXT,
            firma       TEXT,
            job_type    TEXT DEFAULT 'wholesale',
            status      TEXT DEFAULT 'uploaded',
            filename    TEXT,
            filepath    TEXT,
            row_count   INTEGER DEFAULT 0,
            result_json TEXT,
            error       TEXT,
            meta_json   TEXT,
            zero_retention INTEGER DEFAULT 1,
            purge_after TEXT
        )
        """
    )
    cols = {r[1] for r in db.execute("PRAGMA table_info(b2b_jobs)").fetchall()}
    if "zero_retention" not in cols:
        db.execute("ALTER TABLE b2b_jobs ADD COLUMN zero_retention INTEGER DEFAULT 1")
    if "purge_after" not in cols:
        db.execute("ALTER TABLE b2b_jobs ADD COLUMN purge_after TEXT")
    db.commit()
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)


def _row(r: sqlite3.Row | None) -> dict[str, Any] | None:
    if not r:
        return None
    d = dict(r)
    for key in ("result_json", "meta_json"):
        raw = d.get(key)
        if raw:
            try:
                d[key.replace("_json", "")] = json.loads(raw)
            except Exception:
                d[key.replace("_json", "")] = None
        else:
            d[key.replace("_json", "")] = None
    d.pop("result_json", None)
    d.pop("meta_json", None)
    d["zero_retention"] = bool(d.get("zero_retention"))
    return d


def create_job(
    db: sqlite3.Connection,
    *,
    kunde_id: str,
    firma: str,
    filename: str,
    content: bytes,
    job_type: str = "wholesale",
    zero_retention: bool = True,
    retention_hours: int | None = None,
) -> dict[str, Any]:
    ensure_tables(db)
    job_id = uuid.uuid4().hex[:12]
    kid = (kunde_id or "DEMO").upper()[:32]
    safe_name = "".join(c for c in (filename or "upload.csv") if c.isalnum() or c in "._-")[:80]
    folder = UPLOAD_ROOT / kid
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{job_id}_{safe_name}"
    path.write_bytes(content)
    hours = int(retention_hours if retention_hours is not None else DEFAULT_RETENTION_HOURS)
    hours = max(1, min(hours, 168))
    zr = 1 if zero_retention else 0
    if zr:
        db.execute(
            """
            INSERT INTO b2b_jobs (
              id, kunde_id, firma, job_type, status, filename, filepath,
              zero_retention, purge_after
            )
            VALUES (?,?,?,?, 'uploaded', ?, ?, 1, datetime('now', ?))
            """,
            (job_id, kid, (firma or "")[:120], job_type, safe_name, str(path), f"+{hours} hours"),
        )
    else:
        db.execute(
            """
            INSERT INTO b2b_jobs (
              id, kunde_id, firma, job_type, status, filename, filepath,
              zero_retention, purge_after
            )
            VALUES (?,?,?,?, 'uploaded', ?, ?, 0, NULL)
            """,
            (job_id, kid, (firma or "")[:120], job_type, safe_name, str(path)),
        )
    db.commit()
    return get_job(db, job_id) or {"id": job_id, "status": "uploaded"}


def get_job(db: sqlite3.Connection, job_id: str) -> dict[str, Any] | None:
    ensure_tables(db)
    cur = db.execute("SELECT * FROM b2b_jobs WHERE id = ?", (job_id,))
    return _row(cur.fetchone())


def list_jobs(db: sqlite3.Connection, kunde_id: str, limit: int = 30) -> list[dict[str, Any]]:
    ensure_tables(db)
    kid = (kunde_id or "DEMO").upper()
    cur = db.execute(
        "SELECT * FROM b2b_jobs WHERE kunde_id = ? ORDER BY created_at DESC LIMIT ?",
        (kid, limit),
    )
    return [_row(r) for r in cur.fetchall() if r]


def _parse_csv(content: bytes) -> list[dict[str, Any]]:
    text = content.decode("utf-8-sig", errors="replace")
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
    except Exception:
        dialect = csv.excel
        dialect.delimiter = ";" if sample.count(";") >= sample.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    rows: list[dict[str, Any]] = []
    for raw in reader:
        if not raw:
            continue
        norm = {_norm_key(k): (v or "").strip() for k, v in raw.items() if k}
        ean = norm.get("ean") or norm.get("gtin") or norm.get("artikel") or ""
        name = norm.get("name") or norm.get("titel") or norm.get("bezeichnung") or ""
        einkauf = _num(norm.get("einkauf") or norm.get("ek") or norm.get("cost") or norm.get("einkaufspreis"))
        vk = _num(norm.get("vk") or norm.get("verkauf") or norm.get("price") or norm.get("vkp") or norm.get("preis"))
        if not ean and not name and einkauf is None and vk is None:
            continue
        amazon_fee = round((vk or 0) * 0.15, 2) if vk else 0.0
        marge = None
        if vk is not None and einkauf is not None:
            marge = round(vk - einkauf - amazon_fee, 2)
        marge_pct = round((marge / vk) * 100, 1) if marge is not None and vk else None
        rows.append(
            {
                "ean": ean,
                "name": name,
                "einkauf": einkauf,
                "vk": vk,
                "amazon_gebuehr_schaetzung": amazon_fee,
                "marge": marge,
                "marge_pct": marge_pct,
            }
        )
    return rows


def _norm_key(k: str) -> str:
    k = (k or "").strip().lower()
    k = k.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return "".join(c if c.isalnum() else "_" for c in k).strip("_")


def _num(v: str | None) -> float | None:
    if v is None or v == "":
        return None
    s = str(v).strip().replace("€", "").replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def run_job_local(db: sqlite3.Connection, job_id: str) -> dict[str, Any]:
    """MVP-Kalkulation ohne Keepa. n8n kann spaeter ueber Callback ersetzen."""
    job = get_job(db, job_id)
    if not job:
        return {"ok": False, "error": "Job nicht gefunden"}
    if job.get("status") == "purged":
        return {"ok": False, "error": "Rohdaten bereits geloescht (Zero-Retention)"}
    path = Path(job.get("filepath") or "")
    if not path.is_file():
        return {"ok": False, "error": "Datei fehlt"}
    db.execute(
        "UPDATE b2b_jobs SET status='running', updated_at=datetime('now'), error=NULL WHERE id=?",
        (job_id,),
    )
    db.commit()
    try:
        rows = _parse_csv(path.read_bytes())
        ranked = sorted(
            [r for r in rows if r.get("marge") is not None],
            key=lambda r: r["marge"],
            reverse=True,
        )
        result = {
            "engine": "local-mvp",
            "note": "Ohne Keepa: Marge = VK - EK - 15% Schaetzung Amazon-Gebuehr. Keepa spaeter optional.",
            "zero_retention": bool(job.get("zero_retention")),
            "purge_after": job.get("purge_after"),
            "rows": rows[:500],
            "top_margen": ranked[:20],
            "stats": {
                "zeilen": len(rows),
                "mit_marge": len(ranked),
                "beste_marge": ranked[0]["marge"] if ranked else None,
            },
        }
        db.execute(
            """
            UPDATE b2b_jobs
            SET status='done', row_count=?, result_json=?, updated_at=datetime('now'), error=NULL
            WHERE id=?
            """,
            (len(rows), json.dumps(result, ensure_ascii=False), job_id),
        )
        db.commit()
        return {"ok": True, "job": get_job(db, job_id)}
    except Exception as exc:
        db.execute(
            "UPDATE b2b_jobs SET status='error', error=?, updated_at=datetime('now') WHERE id=?",
            (str(exc)[:300], job_id),
        )
        db.commit()
        return {"ok": False, "error": str(exc)[:300], "job": get_job(db, job_id)}


def apply_callback(db: sqlite3.Connection, job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    job = get_job(db, job_id)
    if not job:
        return {"ok": False, "error": "Job nicht gefunden"}
    status = (payload.get("status") or "done").strip()
    result = payload.get("result")
    if result is None and payload.get("rows") is not None:
        result = {"rows": payload.get("rows"), "engine": "n8n"}
    err = (payload.get("error") or "")[:300] or None
    row_count = int(payload.get("row_count") or 0)
    if not row_count and isinstance(result, dict):
        row_count = len(result.get("rows") or [])
    db.execute(
        """
        UPDATE b2b_jobs
        SET status=?, result_json=?, error=?, row_count=?, updated_at=datetime('now')
        WHERE id=?
        """,
        (
            status,
            json.dumps(result, ensure_ascii=False) if result is not None else None,
            err,
            row_count,
            job_id,
        ),
    )
    db.commit()
    return {"ok": True, "job": get_job(db, job_id)}


def _purge_one(db: sqlite3.Connection, job: dict[str, Any]) -> dict[str, Any]:
    """Loescht Upload-Datei und Rohzeilen, behält nur Aggregat-Stats."""
    job_id = job["id"]
    path = Path(job.get("filepath") or "")
    file_deleted = False
    if path.is_file():
        try:
            path.unlink()
            file_deleted = True
        except OSError:
            file_deleted = False
    prev = job.get("result") or {}
    stats = prev.get("stats") if isinstance(prev, dict) else None
    stub = {
        "engine": prev.get("engine") if isinstance(prev, dict) else None,
        "purged": True,
        "purged_at": None,
        "note": "Rohdaten unwiderruflich geloescht (Zero-Retention).",
        "stats": stats or {"zeilen": job.get("row_count") or 0},
        "top_margen": [],
        "rows": [],
    }
    db.execute(
        """
        UPDATE b2b_jobs
        SET status='purged', filepath='', result_json=?, updated_at=datetime('now'), error=NULL
        WHERE id=?
        """,
        (json.dumps(stub, ensure_ascii=False), job_id),
    )
    return {"id": job_id, "file_deleted": file_deleted}


def purge_expired_jobs(db: sqlite3.Connection) -> dict[str, Any]:
    """Zero-Retention: Jobs mit abgelaufenem purge_after bereinigen."""
    ensure_tables(db)
    cur = db.execute(
        """
        SELECT * FROM b2b_jobs
        WHERE zero_retention = 1
          AND status != 'purged'
          AND purge_after IS NOT NULL
          AND purge_after <= datetime('now')
        """
    )
    jobs = [_row(r) for r in cur.fetchall() if r]
    purged = []
    for job in jobs:
        if job:
            purged.append(_purge_one(db, job))
    db.commit()
    return {"ok": True, "purged_count": len(purged), "jobs": purged, "hours_default": DEFAULT_RETENTION_HOURS}


def security_facts() -> dict[str, Any]:
    """Vendor-Assessment Fakten (ehrlich, kein Helsinki-Mythos)."""
    return {
        "hosting": {
            "provider": "Hetzner Cloud",
            "region": "Deutschland (Nuernberg)",
            "not": "Kein Live-Hosting mehr in Helsinki/Finnland",
            "iso27001_provider": True,
            "av_vertrag": "Hetzner AVV in Console herunterladen und zu den Akten (siehe docs/agency/hetzner-avv.md)",
        },
        "encryption": {
            "in_transit": "HTTPS/TLS (Nginx + ggf. Cloudflare vor Domain)",
            "at_rest_app": "SQLite derzeit ohne App-Layer-Verschluesselung",
            "at_rest_provider": "Hetzner-Infrastruktur laut Anbieter; App-LUKS nur nach explizitem OK",
            "n8n_credentials": "N8N_ENCRYPTION_KEY fuer Credentials",
        },
        "retention": {
            "b2b_zero_retention_default_hours": DEFAULT_RETENTION_HOURS,
            "b2b_option": "Upload mit zero_retention=1 loescht Rohdatei + Zeilen nach Frist",
            "ops_logs": "message_log/inbox_log Purge 90 Tage (nightly_watchdog)",
        },
        "access": {
            "portal_auth": "Agency-Passwort oder B2B_PORTAL_TOKEN",
            "no_ghl": True,
        },
    }


def stats_for_kunde(db: sqlite3.Connection, kunde_id: str) -> dict[str, Any]:
    ensure_tables(db)
    kid = (kunde_id or "DEMO").upper()
    cur = db.execute(
        """
        SELECT
          COUNT(*) AS jobs,
          SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) AS done,
          SUM(CASE WHEN status='purged' THEN 1 ELSE 0 END) AS purged,
          SUM(CASE WHEN job_type='buchhaltung' AND status='done' THEN 1 ELSE 0 END) AS buchhaltung_done
        FROM b2b_jobs WHERE kunde_id=?
        """,
        (kid,),
    )
    r = cur.fetchone()
    return {
        "kunde_id": kid,
        "jobs_gesamt": r["jobs"] if r else 0,
        "jobs_fertig": r["done"] if r else 0,
        "jobs_purged": r["purged"] if r else 0,
        "buchhaltung_laeufe": r["buchhaltung_done"] if r else 0,
        "zero_retention_hours": DEFAULT_RETENTION_HOURS,
        "hinweis": "Buchhaltungs-Tab: Zaehler aus Portal-Jobs. Lexware = bestehender n8n-Pfad.",
    }
