"""Router WF1 – Absicherung: Tenant-Trennung, PII-Redaktion, Audit ohne Klartext-Datenleck."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sqlite3
import uuid
from typing import Any

# Kein Helsinki-Mythos
HOSTING_TRUTH = "Hetzner Cloud DE (Nuernberg), EU – nicht Helsinki/Finnland als Live-Standort"

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(
    r"(?<!\w)(?:\+?\d{1,3}[\s\-/]?)?(?:\(?\d{2,5}\)?[\s\-/]?)?\d{3,4}[\s\-/]?\d{3,6}(?!\w)"
)
IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b")
# lange Tokens / Keys
SECRETISH_RE = re.compile(
    r"(?i)\b(api[_-]?key|token|password|passwort|secret|bearer)\s*[:=]\s*\S+"
)


def normalize_tenant(kunde_id: str | None, source: str = "") -> str:
    raw = (kunde_id or "").strip().upper()
    if not raw:
        return "AGENCY"
    # nur sichere Zeichen
    cleaned = re.sub(r"[^A-Z0-9_\-]", "", raw)[:32]
    return cleaned or "AGENCY"


def detect_pii(text: str) -> dict[str, bool]:
    t = text or ""
    return {
        "email": bool(EMAIL_RE.search(t)),
        "phone": bool(PHONE_RE.search(t)),
        "iban": bool(IBAN_RE.search(t)),
        "secretish": bool(SECRETISH_RE.search(t)),
    }


def has_pii(text: str) -> bool:
    d = detect_pii(text)
    return any(d.values())


def redact_pii(text: str) -> str:
    """Ersetzt erkennbare PII fuer Logs/LLM/Audit."""
    if not text:
        return ""
    out = EMAIL_RE.sub("[EMAIL]", text)
    out = IBAN_RE.sub("[IBAN]", out)
    out = SECRETISH_RE.sub(r"\1=[REDACTED]", out)
    # Telefon vorsichtig (nach E-Mail), lange Ziffernfolgen
    out = PHONE_RE.sub("[TEL]", out)
    return out


def fingerprint(text: str, tenant: str) -> str:
    """Nicht umkehrbarer Fingerprint fuer Audit-Korrelation."""
    secret = (os.getenv("ROUTER_AUDIT_KEY") or os.getenv("CRON_SECRET") or "router-local").encode()
    msg = f"{tenant}|{(text or '')[:4000]}".encode("utf-8", errors="replace")
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()[:24]


def llm_allowed_for_message(text: str) -> tuple[bool, str]:
    """OpenAI-Router nur wenn erlaubt und keine PII (Default sicher)."""
    if os.getenv("AGENCY_ROUTER_LLM", "").strip().lower() not in ("1", "true", "yes"):
        return False, "llm_disabled"
    if has_pii(text) and os.getenv("AGENCY_ROUTER_LLM_ALLOW_PII", "").strip() not in ("1", "true", "yes"):
        return False, "pii_blocked"
    return True, "ok"


def ensure_tables(db: sqlite3.Connection) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS router_audit (
            id          TEXT PRIMARY KEY,
            created_at  TEXT DEFAULT (datetime('now')),
            tenant_id   TEXT,
            source      TEXT,
            agents_json TEXT,
            pii_flags   TEXT,
            fingerprint TEXT,
            message_redacted TEXT,
            meta_json   TEXT
        )
        """
    )
    db.commit()


def write_audit(
    db: sqlite3.Connection,
    *,
    tenant_id: str,
    source: str,
    message: str,
    agents: list[str],
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ensure_tables(db)
    aid = uuid.uuid4().hex[:12]
    red = redact_pii(message or "")
    flags = detect_pii(message or "")
    row = {
        "id": aid,
        "tenant_id": tenant_id,
        "source": (source or "")[:40],
        "agents": agents,
        "pii_flags": flags,
        "fingerprint": fingerprint(message or "", tenant_id),
        "message_redacted": red[:2000],
    }
    db.execute(
        """
        INSERT INTO router_audit (id, tenant_id, source, agents_json, pii_flags, fingerprint, message_redacted, meta_json)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        (
            aid,
            tenant_id,
            row["source"],
            json.dumps(agents, ensure_ascii=False),
            json.dumps(flags, ensure_ascii=False),
            row["fingerprint"],
            row["message_redacted"],
            json.dumps(meta or {}, ensure_ascii=False),
        ),
    )
    db.commit()
    return row


def sanitize_result(result: dict[str, Any], *, redact_payload: bool = True) -> dict[str, Any]:
    """Response haerten: PII in payload/context redigieren, Security-Meta anhaengen."""
    out = dict(result)
    if redact_payload:
        if out.get("payload"):
            out["payload"] = redact_pii(str(out["payload"]))
        if out.get("context"):
            out["context"] = redact_pii(str(out["context"]))[:500]
        if out.get("ziel"):
            out["ziel"] = redact_pii(str(out["ziel"]))[:300]
    out["security"] = {
        "hosting": HOSTING_TRUTH,
        "pii_redacted": bool(redact_payload),
        "external_llm": "nur mit AGENCY_ROUTER_LLM=1 und ohne PII (sonst Regel-Engine)",
        "audit": "router_audit speichert nur redigierte Texte + Fingerprint",
        "tenant_isolation": "kunde_id/tenant_id trennt Audit und Playbook-Kontext",
        "kein_chatgpt_pflicht": True,
        "hinweis": (
            "Kein Ersatz fuer AVV/Anwalt. Christian kann weiterhin Daten falsch teilen – "
            "Router blockiert PII an externe LLMs standardmaessig."
        ),
    }
    return out


def security_status() -> dict[str, Any]:
    return {
        "ok": True,
        "workflow": 1,
        "hosting": HOSTING_TRUTH,
        "controls": [
            "Auth Pflicht (Cron/Agency)",
            "Rate-Limit",
            "PII-Redaktion in Response/Audit",
            "LLM-PII-Block (Default)",
            "Tenant-ID fuer Audit-Trennung",
            "Zero-Retention B2B separat (/api/b2b)",
        ],
        "env": {
            "AGENCY_ROUTER_LLM": os.getenv("AGENCY_ROUTER_LLM", ""),
            "AGENCY_ROUTER_LLM_ALLOW_PII": os.getenv("AGENCY_ROUTER_LLM_ALLOW_PII", ""),
            "ROUTER_AUDIT_KEY_set": bool((os.getenv("ROUTER_AUDIT_KEY") or "").strip()),
        },
    }
