# -*- coding: utf-8 -*-
"""Limited-production pilot guards for crm.prospect_create only."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger("nils_job_runtime.crm_prospect_pilot")

PILOT_MAX_DEFAULT = 5
CONFIRM_TTL_DEFAULT = 600  # seconds
LIFECYCLE = "PROSPECT"

_CONFIRM_RE = re.compile(
    r"(?i)^\s*(?:ja(?:\s*,?\s*anlegen)?|anlegen|bestätigen|bestaetigen)\s*[.!]*\s*$"
)

_LEGAL_STRIP = re.compile(
    r"(?i)\b(?:gmbh|ug|ag|kg|mbh|gbr|ohg|e\.?\s*k\.?|ek|ltd|inc)\b"
)


def pilot_max() -> int:
    try:
        return max(1, int(os.getenv("NILS_PROSPECT_PILOT_MAX") or PILOT_MAX_DEFAULT))
    except Exception:
        return PILOT_MAX_DEFAULT


def confirm_ttl_sec() -> int:
    try:
        return max(60, int(os.getenv("NILS_PROSPECT_CONFIRM_TTL_SEC") or CONFIRM_TTL_DEFAULT))
    except Exception:
        return CONFIRM_TTL_DEFAULT


def state_path() -> Path:
    raw = (os.getenv("NILS_PROSPECT_PILOT_STATE") or "").strip()
    if raw:
        return Path(raw)
    return Path("/root/app/data/nils-prospect-pilot-state.json")


def audit_dir() -> Path:
    raw = (os.getenv("NILS_PROSPECT_PILOT_AUDIT_DIR") or "").strip()
    if raw:
        return Path(raw)
    return Path("/root/app/data/nils-prospect-pilot-audit")


def normalize_company_name(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip())[:200]


def match_key(name: str) -> str:
    n = normalize_company_name(name).lower()
    n = _LEGAL_STRIP.sub(" ", n)
    return re.sub(r"[^a-z0-9äöüß]+", "", n)


def is_confirm_text(text: str) -> bool:
    return bool(_CONFIRM_RE.match((text or "").strip()))


def payload_dict(
    *,
    company: str,
    contact: str = "",
    email: str = "",
    phone: str = "",
    country: str = "",
    legal_basis: str = "",
    outbound_allowed: str = "false",
    lifecycle: str = LIFECYCLE,
) -> dict[str, str]:
    out_raw = (outbound_allowed or "false").strip().lower()
    outbound = "true" if out_raw in ("1", "true", "yes", "ja") else "false"
    return {
        "company": normalize_company_name(company),
        "contact": re.sub(r"\s+", " ", (contact or "").strip())[:200],
        "email": (email or "").strip().lower()[:200],
        "phone": re.sub(r"\s+", "", (phone or "").strip())[:40],
        "country": (country or "").strip().upper()[:8],
        "legal_basis": (legal_basis or "").strip()[:40],
        "outbound_allowed": outbound,
        "lifecycle": (lifecycle or LIFECYCLE).strip().upper(),
    }


_COUNTRY_DE_RE = re.compile(
    r"(?i)\b(?:deutschland|germany|bundesrepublik\s+deutschland)\b"
    r"|(?:^|[\s,;])(?:land|standort)\s*[:=]?\s*de(?:$|[\s,;.])"
    r"|(?:^|[\s,;])in\s+deutschland(?:$|[\s,;.])"
)

_LEGAL_BASIS_RULES: list[tuple[re.Pattern[str], str, str]] = [
    (
        re.compile(
            r"(?i)rechtsgrundlage\s*[:=]?\s*(?:art\.?\s*)?6\s*(?:abs\.?\s*)?1\s*"
            r"(?:lit\.?\s*)?f|rechtsgrundlage\s*[:=]?\s*berechtigtes\s+interesse"
        ),
        "art6_1_f",
        "Art. 6 Abs. 1 lit. f DSGVO (berechtigtes Interesse)",
    ),
    (
        re.compile(
            r"(?i)rechtsgrundlage\s*[:=]?\s*(?:art\.?\s*)?6\s*(?:abs\.?\s*)?1\s*"
            r"(?:lit\.?\s*)?a|rechtsgrundlage\s*[:=]?\s*einwilligung"
        ),
        "art6_1_a",
        "Art. 6 Abs. 1 lit. a DSGVO (Einwilligung)",
    ),
    (
        re.compile(
            r"(?i)rechtsgrundlage\s*[:=]?\s*(?:art\.?\s*)?6\s*(?:abs\.?\s*)?1\s*"
            r"(?:lit\.?\s*)?b|rechtsgrundlage\s*[:=]?\s*vertrag"
        ),
        "art6_1_b",
        "Art. 6 Abs. 1 lit. b DSGVO (Vertrag)",
    ),
]

LEGAL_BASIS_LABELS = {
    "": "noch nicht bewertet",
    "art6_1_f": "Art. 6 Abs. 1 lit. f DSGVO (berechtigtes Interesse)",
    "art6_1_a": "Art. 6 Abs. 1 lit. a DSGVO (Einwilligung)",
    "art6_1_b": "Art. 6 Abs. 1 lit. b DSGVO (Vertrag)",
}


def extract_country_from_text(text: str) -> str:
    t = text or ""
    if _COUNTRY_DE_RE.search(t):
        return "DE"
    return ""


def extract_legal_basis_from_text(text: str) -> str:
    """Only explicit, validated phrases — never invent art6_1_f."""
    t = text or ""
    for rx, code, _label in _LEGAL_BASIS_RULES:
        if rx.search(t):
            return code
    return ""


def legal_basis_label(code: str) -> str:
    return LEGAL_BASIS_LABELS.get((code or "").strip(), code or LEGAL_BASIS_LABELS[""])


def payload_hash(payload: dict[str, str]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def format_preview(payload: dict[str, str]) -> str:
    def _v(key: str, label: str) -> str:
        v = (payload.get(key) or "").strip()
        return f"{label}: {v if v else 'nicht angegeben'}"

    country = (payload.get("country") or "").strip()
    legal = (payload.get("legal_basis") or "").strip()
    outbound = (payload.get("outbound_allowed") or "false").strip().lower() == "true"
    lines = [
        "Ich würde folgenden Interessenten anlegen:",
        "",
        f"Unternehmen: {payload.get('company') or 'nicht angegeben'}",
        f"Lifecycle: {payload.get('lifecycle') or LIFECYCLE}",
        _v("contact", "Ansprechpartner"),
        _v("email", "E-Mail"),
        _v("phone", "Telefon"),
        f"Land: {country if country else 'nicht angegeben'}",
        f"Rechtsgrundlage: {legal_basis_label(legal)}",
        f"Outbound: {'freigegeben' if outbound else 'nicht freigegeben'}",
        "",
        "Soll ich den Datensatz jetzt anlegen?",
        "Antwort: Ja / Anlegen / Bestätigen / Ja, anlegen — sonst Abbrechen.",
    ]
    return "\n".join(lines)


def bind_preview(
    turn: dict[str, Any],
    *,
    chat_id: str,
    owner_id: str,
    job_id: str,
    payload: dict[str, str],
) -> dict[str, Any]:
    collected = dict(turn.get("collected_parameters") or {})
    h = payload_hash(payload)
    now = time.time()
    binding = {
        "chat_id": str(chat_id),
        "owner_id": str(owner_id or chat_id),
        "job_id": str(job_id),
        "company_norm": payload["company"],
        "contact_norm": payload.get("contact") or "",
        "payload": payload,
        "payload_hash": h,
        "preview_at": now,
        "expires_at": now + confirm_ttl_sec(),
        "confirmed": False,
    }
    collected["pilot_binding"] = binding
    collected["company"] = payload["company"]
    collected["customer"] = payload["company"]
    collected["contact"] = payload.get("contact") or ""
    collected["email"] = payload.get("email") or ""
    collected["phone"] = payload.get("phone") or ""
    collected["country"] = payload.get("country") or ""
    collected["legal_basis"] = payload.get("legal_basis") or ""
    collected["outbound_allowed"] = payload.get("outbound_allowed") or "false"
    turn["collected_parameters"] = collected
    return binding


def validate_confirmation(
    turn: dict[str, Any],
    *,
    chat_id: str,
    owner_id: str,
    job_id: str,
    text: str,
) -> tuple[bool, str, dict[str, Any] | None]:
    if not is_confirm_text(text):
        return False, "confirm_phrase_rejected", None
    collected = dict(turn.get("collected_parameters") or {})
    binding = collected.get("pilot_binding") or {}
    if not binding:
        return False, "no_preview_binding", None
    if binding.get("confirmed"):
        return False, "confirmation_already_used", None
    if str(binding.get("job_id") or "") != str(job_id):
        return False, "job_id_mismatch", None
    if str(binding.get("chat_id") or "") != str(chat_id):
        return False, "chat_id_mismatch", None
    expected_owner = str(binding.get("owner_id") or "")
    actual_owner = str(owner_id or chat_id)
    if expected_owner and expected_owner != actual_owner:
        return False, "owner_id_mismatch", None
    exp = float(binding.get("expires_at") or 0)
    if time.time() > exp:
        return False, "confirmation_expired", None
    payload = dict(binding.get("payload") or {})
    # Recompute from current collected — field change forces new preview
    current = payload_dict(
        company=collected.get("company") or collected.get("customer") or "",
        contact=collected.get("contact") or "",
        email=collected.get("email") or "",
        phone=collected.get("phone") or "",
        country=collected.get("country") or "",
        legal_basis=collected.get("legal_basis") or "",
        outbound_allowed=collected.get("outbound_allowed") or "false",
        lifecycle=collected.get("lifecycle") or LIFECYCLE,
    )
    if payload_hash(current) != binding.get("payload_hash"):
        return False, "payload_changed", None
    if payload_hash(payload) != binding.get("payload_hash"):
        return False, "payload_hash_mismatch", None
    return True, "ok", binding


def mark_confirmed(turn: dict[str, Any]) -> None:
    collected = dict(turn.get("collected_parameters") or {})
    binding = dict(collected.get("pilot_binding") or {})
    binding["confirmed"] = True
    binding["confirmed_at"] = time.time()
    collected["pilot_binding"] = binding
    turn["collected_parameters"] = collected


def load_state() -> dict[str, Any]:
    p = state_path()
    try:
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        log.exception("pilot_state_load")
    return {
        "success_count": 0,
        "record_ids": [],
        "disabled": False,
        "disable_reason": "",
        "events": [],
    }


def save_state(state: dict[str, Any]) -> None:
    p = state_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        log.exception("pilot_state_save")


def success_count() -> int:
    return int(load_state().get("success_count") or 0)


def pilot_exhausted() -> bool:
    st = load_state()
    if st.get("disabled"):
        return True
    return success_count() >= pilot_max()


def disable_capability(reason: str) -> None:
    """Flip NILS_CAP_CRM_PROSPECT_CREATE=0 in process + .env if present."""
    os.environ["NILS_CAP_CRM_PROSPECT_CREATE"] = "0"
    st = load_state()
    st["disabled"] = True
    st["disable_reason"] = (reason or "")[:300]
    st["disabled_at"] = datetime.now(timezone.utc).isoformat()
    save_state(st)
    env_path = Path(os.getenv("NILS_BACKEND_ENV") or "/root/app/backend/.env")
    try:
        if env_path.is_file():
            lines = env_path.read_text(encoding="utf-8").splitlines()
            out = []
            seen = False
            for line in lines:
                if line.startswith("NILS_CAP_CRM_PROSPECT_CREATE="):
                    out.append("NILS_CAP_CRM_PROSPECT_CREATE=0")
                    seen = True
                else:
                    out.append(line)
            if not seen:
                out.append("NILS_CAP_CRM_PROSPECT_CREATE=0")
            env_path.write_text("\n".join(out) + "\n", encoding="utf-8")
            log.warning("pilot_cap_disabled reason=%s", reason)
    except Exception:
        log.exception("pilot_cap_disable_env")


def record_success(*, record_id: int, company: str, job_id: str) -> int:
    st = load_state()
    st["success_count"] = int(st.get("success_count") or 0) + 1
    ids = list(st.get("record_ids") or [])
    ids.append(
        {
            "id": int(record_id),
            "company": company,
            "job_id": job_id,
            "at": datetime.now(timezone.utc).isoformat(),
        }
    )
    st["record_ids"] = ids[-20:]
    save_state(st)
    n = int(st["success_count"])
    if n >= pilot_max():
        disable_capability(f"pilot_limit_reached:{n}")
    return n


def emergency_stop(reason: str) -> None:
    disable_capability(reason)
    log.error("pilot_emergency_stop %s", reason)


def find_duplicate_candidates(
    *,
    company_name: str,
    email: str = "",
    phone: str = "",
    contact_name: str = "",
) -> dict[str, Any]:
    """Return exact / fuzzy candidates. No merge."""
    from nils_job_runtime import crm_offer_service as offer_svc
    from nils_job_runtime import crm_prospect_service as crm

    name = normalize_company_name(company_name)
    key = match_key(name)
    exact = crm.find_exact(name)
    fuzzy: list[dict[str, Any]] = []
    email_hits: list[dict[str, Any]] = []
    phone_hits: list[dict[str, Any]] = []

    con = offer_svc._connect(readonly=True)
    try:
        tenant = offer_svc.tenant_id()
        rows = con.execute(
            """
            SELECT id, name,
                   COALESCE(lifecycle_status, '') AS lifecycle_status,
                   COALESCE(customer_number, '') AS customer_number
            FROM companies
            WHERE tenant_id = ?
            ORDER BY id DESC
            LIMIT 500
            """,
            (tenant,),
        ).fetchall()
        for r in rows:
            nm = str(r["name"] or "")
            if exact and int(r["id"]) == int(exact["id"]):
                continue
            mk = match_key(nm)
            if not mk or not key:
                continue
            if mk == key or (len(key) >= 4 and (key in mk or mk in key)):
                fuzzy.append(
                    {
                        "id": int(r["id"]),
                        "name": nm,
                        "lifecycle_status": str(r["lifecycle_status"] or ""),
                        "customer_number": str(r["customer_number"] or ""),
                        "match": "name_similar",
                    }
                )
        if email:
            try:
                erows = con.execute(
                    """
                    SELECT c.id, c.name, COALESCE(c.lifecycle_status,'') AS lifecycle_status
                    FROM companies c
                    JOIN contacts ct ON ct.company_id = c.id
                    WHERE c.tenant_id = ? AND lower(COALESCE(ct.email,'')) = lower(?)
                    LIMIT 10
                    """,
                    (tenant, email),
                ).fetchall()
                email_hits = [
                    {
                        "id": int(x["id"]),
                        "name": str(x["name"] or ""),
                        "lifecycle_status": str(x["lifecycle_status"] or ""),
                        "match": "email",
                    }
                    for x in erows
                ]
            except Exception:
                pass
        if phone:
            digits = re.sub(r"\D+", "", phone)
            if len(digits) >= 6:
                try:
                    prows = con.execute(
                        """
                        SELECT c.id, c.name, COALESCE(c.lifecycle_status,'') AS lifecycle_status,
                               COALESCE(ct.phone,'') AS phone
                        FROM companies c
                        JOIN contacts ct ON ct.company_id = c.id
                        WHERE c.tenant_id = ?
                        LIMIT 200
                        """,
                        (tenant,),
                    ).fetchall()
                    for x in prows:
                        pd = re.sub(r"\D+", "", str(x["phone"] or ""))
                        if pd and (digits in pd or pd in digits):
                            phone_hits.append(
                                {
                                    "id": int(x["id"]),
                                    "name": str(x["name"] or ""),
                                    "lifecycle_status": str(x["lifecycle_status"] or ""),
                                    "match": "phone",
                                }
                            )
                except Exception:
                    pass
        # contact name exact under company (informational)
        contact_hits: list[dict[str, Any]] = []
        if contact_name:
            try:
                crows = con.execute(
                    """
                    SELECT c.id, c.name, ct.name AS contact_name
                    FROM companies c
                    JOIN contacts ct ON ct.company_id = c.id
                    WHERE c.tenant_id = ? AND lower(ct.name) = lower(?)
                    LIMIT 10
                    """,
                    (tenant, contact_name.strip()),
                ).fetchall()
                contact_hits = [
                    {
                        "id": int(x["id"]),
                        "name": str(x["name"] or ""),
                        "contact": str(x["contact_name"] or ""),
                        "match": "contact_name",
                    }
                    for x in crows
                ]
            except Exception:
                pass
    finally:
        con.close()

    if exact:
        return {
            "result": "exact",
            "exact": exact,
            "fuzzy": fuzzy[:5],
            "email_hits": email_hits,
            "phone_hits": phone_hits,
            "contact_hits": contact_hits,
        }
    if email_hits or phone_hits:
        return {
            "result": "uncertain",
            "exact": None,
            "fuzzy": (email_hits + phone_hits + fuzzy)[:5],
            "email_hits": email_hits,
            "phone_hits": phone_hits,
            "contact_hits": contact_hits,
        }
    if fuzzy:
        return {
            "result": "uncertain",
            "exact": None,
            "fuzzy": fuzzy[:5],
            "email_hits": email_hits,
            "phone_hits": phone_hits,
            "contact_hits": contact_hits,
        }
    return {
        "result": "none",
        "exact": None,
        "fuzzy": [],
        "email_hits": [],
        "phone_hits": [],
        "contact_hits": contact_hits if contact_name else [],
    }


def format_duplicate_exact(exact: dict[str, Any]) -> str:
    return (
        "Dieses Unternehmen scheint bereits vorhanden zu sein.\n"
        f"Treffer: {exact.get('name')} (id={exact.get('id')}, "
        f"Lifecycle={exact.get('lifecycle_status') or '—'}).\n"
        "Kein neuer Interessent angelegt."
    )


def format_duplicate_uncertain(cands: list[dict[str, Any]]) -> str:
    lines = [
        "Mögliche bestehende Treffer — bitte prüfen. Keine automatische Zusammenführung.",
    ]
    for i, c in enumerate(cands[:5], 1):
        lines.append(
            f"{i}. {c.get('name')} (id={c.get('id')}, "
            f"{c.get('lifecycle_status') or '—'}, match={c.get('match')})"
        )
    lines.append("Neuen Namen nennen oder mit eindeutigem Firmennamen erneut starten.")
    return "\n".join(lines)


def audit_event(event: dict[str, Any]) -> None:
    """Append structured audit without secrets / full message bodies."""
    safe = dict(event)
    for k in ("text", "user_text", "bot_text", "message"):
        if k in safe and isinstance(safe[k], str):
            safe[k] = safe[k][:120]
    safe.setdefault("ts", datetime.now(timezone.utc).isoformat())
    safe.setdefault("release_id", os.getenv("NILS_RELEASE_ID") or "")
    safe.setdefault("commit", (os.getenv("NILS_GIT_COMMIT") or "")[:40])
    safe.setdefault("digest_tag", os.getenv("NILS_RELEASE_ID") or "")
    try:
        d = audit_dir()
        d.mkdir(parents=True, exist_ok=True)
        day = datetime.now(timezone.utc).strftime("%Y%m%d")
        path = d / f"pilot-{day}.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(safe, ensure_ascii=False) + "\n")
    except Exception:
        log.exception("pilot_audit")
    st = load_state()
    ev = list(st.get("events") or [])
    ev.append({k: safe.get(k) for k in ("ts", "action", "job_id", "record_id", "guard")})
    st["events"] = ev[-100:]
    save_state(st)
