"""Nils WhatsApp Ops: Owner schreibt privat an Business-Nummer → Nils antwortet."""
from __future__ import annotations

import os
import re
import sqlite3
from typing import Any

import nils_ops as nils_ops_svc


def digits_only(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


def owner_phones() -> list[str]:
    """Whitelist: NILS_OPS_OWNER_PHONES (Komma) + OWNER_PHONE + AGENCY_OWNER_PHONE."""
    raw = (
        os.getenv("NILS_OPS_OWNER_PHONES")
        or os.getenv("AGENCY_OWNER_PHONES")
        or ""
    )
    parts = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
    for key in ("OWNER_PHONE", "AGENCY_OWNER_PHONE"):
        v = (os.getenv(key) or "").strip()
        if v:
            parts.append(v)
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        d = digits_only(p)
        if len(d) >= 10 and d not in seen:
            seen.add(d)
            out.append(d)
    return out


def is_owner(phone: str) -> bool:
    d = digits_only(phone)
    if not d:
        return False
    owners = owner_phones()
    if not owners:
        return False
    for o in owners:
        if d == o or d.endswith(o[-10:]) or o.endswith(d[-10:]):
            return True
    return False


def is_agency_inbox(phone_number_id: str) -> bool:
    """True wenn Nachricht auf der Agentur-WABA-Nummer landet (nicht Kunden-Tenant)."""
    agency_id = (os.getenv("WHATSAPP_PHONE_NUMBER_ID") or "").strip()
    pid = (phone_number_id or "").strip()
    if not agency_id:
        # Keine Agency-ID: Owner-Pfad nur wenn Absender Owner ist (Fallback)
        return True
    return bool(pid) and pid == agency_id


def ensure_sessions(db: sqlite3.Connection) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS nils_wa_sessions (
            phone      TEXT PRIMARY KEY,
            pending    TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
        )
        """
    )


def _get_pending(db: sqlite3.Connection, phone: str) -> dict | None:
    ensure_sessions(db)
    import json

    row = db.execute(
        "SELECT pending FROM nils_wa_sessions WHERE phone=?",
        (digits_only(phone),),
    ).fetchone()
    if not row or not row[0]:
        return None
    try:
        return json.loads(row[0])
    except Exception:
        return None


def _set_pending(db: sqlite3.Connection, phone: str, pending: dict | None) -> None:
    ensure_sessions(db)
    import json

    d = digits_only(phone)
    if pending is None:
        db.execute("DELETE FROM nils_wa_sessions WHERE phone=?", (d,))
        return
    db.execute(
        """
        INSERT INTO nils_wa_sessions (phone, pending, updated_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(phone) DO UPDATE SET
          pending=excluded.pending,
          updated_at=datetime('now')
        """,
        (d, json.dumps(pending, ensure_ascii=False)),
    )


def readiness() -> dict[str, Any]:
    token = bool((os.getenv("WHATSAPP_ACCESS_TOKEN") or "").strip())
    phone_id = bool((os.getenv("WHATSAPP_PHONE_NUMBER_ID") or "").strip())
    verify = bool((os.getenv("WHATSAPP_VERIFY_TOKEN") or "").strip())
    owners = owner_phones()
    return {
        "ok": token and phone_id and verify and bool(owners),
        "agent": "nils",
        "channel": "whatsapp_ops",
        "whatsapp_token": token,
        "whatsapp_phone_number_id": phone_id,
        "whatsapp_verify_token": verify,
        "owner_phones_configured": len(owners),
        "owner_phones_masked": [f"…{p[-4:]}" for p in owners],
        "display_phone": (os.getenv("WHATSAPP_DISPLAY_PHONE") or "").strip(),
        "webhook": "https://digitalehandwerkskunst.de/api/whatsapp/webhook",
        "next_steps": _next_steps(token, phone_id, owners),
        "auto_deploy": False,
        "note": "Owner schreibt privat an Business-Nummer. Kein Auto-Deploy ohne Freigabe im Chat.",
    }


def _next_steps(token: bool, phone_id: bool, owners: list[str]) -> list[str]:
    steps = []
    if not token:
        steps.append("WHATSAPP_ACCESS_TOKEN in Agency-Setup eintragen")
    if not phone_id:
        steps.append("WHATSAPP_PHONE_NUMBER_ID in Agency-Setup eintragen")
    if not owners:
        steps.append("OWNER_PHONE oder NILS_OPS_OWNER_PHONES (+49…) setzen – deine Privatnummer")
    if token and phone_id and owners:
        steps.append("Vom Handy an die Business-Nummer schreiben: „Nils Status“")
    else:
        steps.append("Meta Webhook: Callback + Verify-Token + messages")
    return steps


def handle_owner_message(
    db: sqlite3.Connection,
    *,
    phone: str,
    text: str,
    image_bytes: bytes | None = None,
    image_ext: str = "jpg",
) -> dict[str, Any]:
    """Owner-Nachricht → nils_ops.handle_turn → Antworttext."""
    uploads = []
    if image_bytes:
        uploads.append(
            {
                "data": image_bytes,
                "filename": f"wa.{image_ext or 'jpg'}",
                "mime": f"image/{'jpeg' if image_ext in ('jpg', 'jpeg') else image_ext}",
            }
        )
    pending = _get_pending(db, phone)
    confirm = False
    tnorm = (text or "").strip().lower()
    if pending and tnorm in ("ja", "yes", "ok", "okay", "mach", "los", "bestätigen", "bestaetigen"):
        confirm = True
    if pending and tnorm in ("nein", "abbrechen", "cancel", "stop"):
        confirm = False

    # Kurze Ops-Shortcuts ohne LLM
    if tnorm in ("status", "nils status", "dual", "ping", "wach?"):
        ready = readiness()
        reply = (
            "Nils hier. WhatsApp-Ops "
            + ("scharf." if ready.get("ok") else "noch nicht komplett.")
            + f"\nOwner-Nummern: {ready.get('owner_phones_configured')}"
            + f"\nToken: {'ja' if ready.get('whatsapp_token') else 'nein'}"
            + "\nFür Dual/Radar: im Cursor „Dual Status“ oder Radar-Scan."
        )
        return {"ok": True, "reply": reply, "route": "nils_shortcut", "owner": True}

    result = nils_ops_svc.handle_turn(
        db,
        text or "",
        uploads=uploads or None,
        confirm=confirm,
        pending=pending,
    )
    if result.get("pending"):
        _set_pending(db, phone, result["pending"])
    elif confirm or tnorm in ("nein", "abbrechen", "cancel", "stop"):
        _set_pending(db, phone, None)
    elif not result.get("needs_confirm"):
        _set_pending(db, phone, None)

    reply = (result.get("reply") or result.get("error") or "").strip()
    if not reply:
        reply = "Verstanden. Mehr Details oder Foto schicken."
    # WhatsApp-Länge begrenzen
    if len(reply) > 3500:
        reply = reply[:3400] + "\n…(gekürzt, Rest im Ops-Portal)"
    return {
        "ok": not bool(result.get("error")),
        "reply": reply,
        "route": "nils_ops",
        "owner": True,
        "needs_confirm": result.get("needs_confirm"),
    }


def stranger_reply() -> str:
    return (
        "Hier ist die Ops-Nummer von Webschmiede (Nils). "
        "Kundenanfragen bitte über die Website oder die Nummer eures Betriebs. "
        "Danke."
    )
