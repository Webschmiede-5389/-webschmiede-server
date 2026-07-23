"""Agency Workorders: Telegram/API-Aufträge → Umsetzung (soweit sicher).

Direkt ausführbar: Kunden-JSON (Kontakt, Brand-Texte, Status, Notiz).
Alles andere: Auftrag + Handoff für Cursor, kein Blind-HTML-Edit.
"""
from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from stripe_billing import load_kunde, save_kunde

KID_RE = re.compile(r"\b(SHY\d{3})\b", re.I)
ROOT = Path(__file__).resolve().parents[2]
HANDOFF_DIR = Path(
    __import__("os").getenv(
        "WORKORDER_HANDOFF_DIR",
        str(ROOT / "docs" / "memory" / "workorders"),
    )
)

# Whitelist: Pfad in kunden.json → direkt umsetzbar
ALLOWED_PATCHES: dict[str, str] = {
    "status": "status",
    "telefon": "kontakt.telefon",
    "phone": "kontakt.telefon",
    "email": "kontakt.email",
    "adresse": "kontakt.adresse",
    "address": "kontakt.adresse",
    "tisch_promo": "brand.table.promo",
    "tisch_headline": "brand.table.headline",
    "tisch_sub": "brand.table.sub",
    "tisch_hint": "brand.table.hint",
    "google_promo": "brand.google.promo",
    "google_headline": "brand.google.headline",
    "google_sub": "brand.google.sub",
    "review_url": "google.review_url",
    "inhaber": "inhaber",
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_tables(db: sqlite3.Connection) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS agency_workorders (
            id          TEXT PRIMARY KEY,
            created_at  TEXT DEFAULT (datetime('now')),
            updated_at  TEXT DEFAULT (datetime('now')),
            source      TEXT,
            kunde_id    TEXT,
            title       TEXT,
            body        TEXT,
            kind        TEXT,
            status      TEXT DEFAULT 'open',
            patch_json  TEXT,
            result_json TEXT,
            handoff_path TEXT
        )
        """
    )


def _row(r: sqlite3.Row | None) -> dict[str, Any] | None:
    if not r:
        return None
    d = dict(r)
    for key in ("patch_json", "result_json"):
        raw = d.pop(key, None)
        name = key.replace("_json", "")
        if raw:
            try:
                d[name] = json.loads(raw)
            except Exception:
                d[name] = {}
        else:
            d[name] = {}
    return d


def list_orders(db: sqlite3.Connection, *, limit: int = 40, status: str | None = None) -> dict[str, Any]:
    ensure_tables(db)
    if status:
        rows = db.execute(
            """
            SELECT * FROM agency_workorders WHERE status=?
            ORDER BY datetime(created_at) DESC LIMIT ?
            """,
            (status, max(1, min(limit, 100))),
        ).fetchall()
    else:
        rows = db.execute(
            """
            SELECT * FROM agency_workorders
            ORDER BY datetime(created_at) DESC LIMIT ?
            """,
            (max(1, min(limit, 100)),),
        ).fetchall()
    return {"ok": True, "count": len(rows), "orders": [_row(r) for r in rows]}


def get_order(db: sqlite3.Connection, order_id: str) -> dict[str, Any] | None:
    ensure_tables(db)
    r = db.execute("SELECT * FROM agency_workorders WHERE id=?", (order_id,)).fetchone()
    return _row(r)


def _set_path(obj: dict, dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    cur: Any = obj
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value


def _get_path(obj: dict, dotted: str) -> Any:
    cur: Any = obj
    for p in dotted.split("."):
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur


def apply_kunde_patch(kid: str, patch: dict[str, Any]) -> dict[str, Any]:
    """Whitelist-Patch auf kunden/*.json – Live-Umsetzung."""
    loaded = load_kunde(kid)
    if not loaded:
        return {"ok": False, "error": f"Kunde {kid} nicht gefunden"}
    k, path = loaded
    allowed_targets = set(ALLOWED_PATCHES.values())
    applied: list[dict[str, Any]] = []
    for key, val in (patch or {}).items():
        if key == "notiz":
            text = str(val).strip()
            if text:
                k.setdefault("notizen", []).append({"at": _now()[:10], "text": text})
                applied.append({"field": "notiz", "value": text[:200]})
            continue
        dotted = ALLOWED_PATCHES.get(key)
        if not dotted and key in allowed_targets:
            dotted = key
        if not dotted:
            return {
                "ok": False,
                "error": f"Feld nicht erlaubt: {key}",
                "allowed": sorted(ALLOWED_PATCHES.keys()),
            }
        old = _get_path(k, dotted)
        new_val = str(val).strip() if not isinstance(val, (int, float, bool)) else val
        _set_path(k, dotted, new_val)
        applied.append({"field": dotted, "old": old, "new": _get_path(k, dotted)})
    save_kunde(k, path)
    return {"ok": True, "kunde_id": kid.upper(), "applied": applied, "path": str(path)}


def _write_handoff(order: dict[str, Any]) -> str:
    HANDOFF_DIR.mkdir(parents=True, exist_ok=True)
    path = HANDOFF_DIR / f"{order['id']}.md"
    body = (
        f"# Workorder {order['id']}\n\n"
        f"Stand: {_now()}\n\n"
        f"- Status: {order.get('status')}\n"
        f"- Kunde: {order.get('kunde_id') or '–'}\n"
        f"- Art: {order.get('kind')}\n"
        f"- Quelle: {order.get('source')}\n\n"
        f"## Auftrag\n\n{order.get('title')}\n\n{order.get('body')}\n\n"
        f"## Patch\n\n```json\n{json.dumps(order.get('patch') or {}, ensure_ascii=False, indent=2)}\n```\n\n"
        f"## Für Cursor\n\n"
        f"Bitte umsetzen, dann Workorder `{order['id']}` auf done setzen "
        f"(API oder Telegram: „auftrag {order['id']} erledigt“).\n"
    )
    path.write_text(body, encoding="utf-8")
    return str(path)


def create_order(
    db: sqlite3.Connection,
    *,
    title: str,
    body: str = "",
    source: str = "telegram",
    kunde_id: str | None = None,
    kind: str = "general",
    patch: dict[str, Any] | None = None,
    auto_execute: bool = True,
) -> dict[str, Any]:
    ensure_tables(db)
    oid = uuid.uuid4().hex[:10]
    kid = (kunde_id or "").upper() or None
    order = {
        "id": oid,
        "created_at": _now(),
        "source": source,
        "kunde_id": kid,
        "title": (title or "Auftrag")[:200],
        "body": (body or "")[:4000],
        "kind": kind,
        "status": "open",
        "patch": patch or {},
    }
    handoff = _write_handoff(order)
    db.execute(
        """
        INSERT INTO agency_workorders
          (id, source, kunde_id, title, body, kind, status, patch_json, handoff_path)
        VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?)
        """,
        (
            oid,
            source,
            kid,
            order["title"],
            order["body"],
            kind,
            json.dumps(order["patch"], ensure_ascii=False),
            handoff,
        ),
    )
    db.commit()
    order["handoff_path"] = handoff

    if auto_execute and kind == "kunde_patch" and kid and order["patch"]:
        return execute_order(db, oid, confirm=True)

    return {"ok": True, "order": get_order(db, oid), "executed": False, "handoff": handoff}


def execute_order(db: sqlite3.Connection, order_id: str, *, confirm: bool = False) -> dict[str, Any]:
    order = get_order(db, order_id)
    if not order:
        return {"ok": False, "error": "Auftrag unbekannt"}
    if order.get("status") == "done":
        return {"ok": True, "order": order, "skipped": True, "detail": "schon erledigt"}
    if order.get("kind") == "kunde_patch":
        if not confirm and order.get("status") == "needs_confirm":
            return {
                "ok": False,
                "needs_confirm": True,
                "order": order,
                "text": f"Auftrag {order_id}: {order.get('title')}. „ja“ zum Umsetzen.",
            }
        kid = order.get("kunde_id") or ""
        result = apply_kunde_patch(kid, order.get("patch") or {})
        status = "done" if result.get("ok") else "failed"
        db.execute(
            """
            UPDATE agency_workorders
            SET status=?, result_json=?, updated_at=datetime('now')
            WHERE id=?
            """,
            (status, json.dumps(result, ensure_ascii=False), order_id),
        )
        db.commit()
        order = get_order(db, order_id)
        text = (
            f"Umgesetzt: {order_id}\n"
            + json.dumps(result.get("applied") or result, ensure_ascii=False)[:1200]
            if result.get("ok")
            else f"Fehler {order_id}: {result.get('error')}"
        )
        return {"ok": bool(result.get("ok")), "order": order, "result": result, "text": text, "executed": True}

    # Nicht auto-fähig → Handoff bleibt, Status in_progress
    db.execute(
        """
        UPDATE agency_workorders
        SET status='in_progress', updated_at=datetime('now')
        WHERE id=?
        """,
        (order_id,),
    )
    db.commit()
    order = get_order(db, order_id)
    return {
        "ok": True,
        "executed": False,
        "order": order,
        "text": (
            f"Auftrag {order_id} liegt für Cursor/Umsetzung bereit.\n"
            f"Handoff: {order.get('handoff_path')}\n"
            f"{order.get('title')}\n{order.get('body')[:800]}"
        ),
    }


def mark_done(db: sqlite3.Connection, order_id: str, note: str = "") -> dict[str, Any]:
    order = get_order(db, order_id)
    if not order:
        return {"ok": False, "error": "unbekannt"}
    result = dict(order.get("result") or {})
    if note:
        result["done_note"] = note[:500]
    db.execute(
        """
        UPDATE agency_workorders
        SET status='done', result_json=?, updated_at=datetime('now')
        WHERE id=?
        """,
        (json.dumps(result, ensure_ascii=False), order_id),
    )
    db.commit()
    return {"ok": True, "order": get_order(db, order_id)}


def parse_order_message(text: str) -> dict[str, Any] | None:
    """Freitext → Auftrag. Erkennt SHY001 + Feldänderungen oder allgemeinen Website-Auftrag."""
    raw = (text or "").strip()
    if not raw:
        return None
    t = raw.lower()
    # Prefix strip
    for pref in ("auftrag:", "änder:", "aender:", "ändere:", "aendere:", "website:", "setz:", "setze:"):
        if t.startswith(pref):
            raw = raw[len(pref) :].strip()
            t = raw.lower()
            break

    kid_m = KID_RE.search(raw)
    kid = kid_m.group(1).upper() if kid_m else None

    # „erledigt“
    m_done = re.search(r"auftrag\s+([a-f0-9]{8,12})\s+(erledigt|done|fertig)", t)
    if m_done:
        return {"action": "done", "order_id": m_done.group(1)}

    m_exec = re.search(r"auftrag\s+([a-f0-9]{8,12})\s+(ausführen|ausfuehren|umsetzen|ja)", t)
    if m_exec:
        return {"action": "execute", "order_id": m_exec.group(1)}

    # Feld-Patterns
    patch: dict[str, Any] = {}
    patterns = [
        (r"telefon(?:nummer)?\s*(?:auf|ist|=|:)\s*([+\d][\d\s/\-]{5,})", "telefon"),
        (r"(?:mail|e-?mail)\s*(?:auf|ist|=|:)\s*(\S+@\S+)", "email"),
        (r"adresse\s*(?:auf|ist|=|:)\s*(.+)$", "adresse"),
        (r"tisch[-\s]?promo\s*(?:auf|ist|=|:)\s*[„\"]?(.+?)[“\"]?$", "tisch_promo"),
        (r"tisch[-\s]?headline\s*(?:auf|ist|=|:)\s*[„\"]?(.+?)[“\"]?$", "tisch_headline"),
        (r"tisch[-\s]?sub\s*(?:auf|ist|=|:)\s*[„\"]?(.+?)[“\"]?$", "tisch_sub"),
        (r"google[-\s]?promo\s*(?:auf|ist|=|:)\s*[„\"]?(.+?)[“\"]?$", "google_promo"),
        (r"status\s*(?:auf|ist|=|:)\s*(live|test|lead|angebot)\b", "status"),
        (r"notiz\s*(?:auf|:|=)\s*(.+)$", "notiz"),
        (r"review[-\s]?url\s*(?:auf|ist|=|:)\s*(\S+)", "review_url"),
    ]
    for pat, field in patterns:
        m = re.search(pat, raw, re.I | re.M)
        if m:
            patch[field] = m.group(1).strip().strip("„“\"'")

    # „Promo auf dem Tischaufsteller auf X“ 
    m = re.search(r"(?:promo|rabatt[-\s]?text)\s+(?:bei\s+)?(?:SHY\d{3}\s+)?(?:auf|=|:)\s*[„\"]?(.+?)[“\"]?$", raw, re.I)
    if m and "tisch_promo" not in patch:
        patch["tisch_promo"] = m.group(1).strip().strip("„“\"'")

    websiteish = any(
        x in t
        for x in (
            "website",
            "webseite",
            "homepage",
            "landing",
            "hero",
            "impressum",
            "css",
            "design",
            "button",
            "farbe",
        )
    )

    if patch and kid:
        title = f"{kid}: " + ", ".join(f"{k}={str(v)[:40]}" for k, v in patch.items())
        return {
            "action": "create",
            "kind": "kunde_patch",
            "kunde_id": kid,
            "title": title,
            "body": raw,
            "patch": patch,
            "auto_execute": True,
        }

    if patch and not kid:
        return {
            "action": "ask_kunde",
            "patch": patch,
            "body": raw,
            "text": "Für welchen Kunden? Schreib die ID mit, z. B. SHY001.",
        }

    # Sales/Meeting dem Telegram-Agenten überlassen
    if any(
        x in t
        for x in (
            "scan",
            "scann",
            "analys",
            "recherch",
            "einladung",
            "meeting",
            "funnel",
            "deal",
        )
    ):
        return None

    # Allgemeiner Umsetzungsauftrag (Cursor-Handoff) – klarer Trigger
    explicit = any(
        t.startswith(p)
        for p in (
            "auftrag",
            "änder",
            "aender",
            "website:",
            "webseite:",
            "umsetzen:",
            "implement",
        )
    ) or any(x in t for x in ("bitte umsetzen", "cursor:", "handoff:"))
    if explicit or (websiteish and any(x in t for x in ("änder", "aender", "mach den", "setz den", "update"))):
        return {
            "action": "create",
            "kind": "cursor_handoff" if websiteish or not kid else "general",
            "kunde_id": kid,
            "title": (raw[:120] + "…") if len(raw) > 120 else raw,
            "body": raw,
            "patch": {},
            "auto_execute": False,
        }
    return None


def handle_message(db: sqlite3.Connection, text: str, *, source: str = "telegram") -> dict[str, Any] | None:
    """Wenn Text ein Auftrag ist → anlegen/ausführen. Sonst None."""
    parsed = parse_order_message(text)
    if not parsed:
        return None
    if parsed.get("action") == "ask_kunde":
        return {"ok": False, "reply": parsed.get("text"), "route": "workorder_ask"}
    if parsed.get("action") == "done":
        r = mark_done(db, parsed["order_id"])
        return {
            "ok": r.get("ok"),
            "reply": f"Auftrag {parsed['order_id']} als erledigt markiert.",
            "route": "workorder_done",
            "order": r.get("order"),
        }
    if parsed.get("action") == "execute":
        r = execute_order(db, parsed["order_id"], confirm=True)
        return {
            "ok": r.get("ok"),
            "reply": r.get("text") or "Ausgeführt.",
            "route": "workorder_exec",
            "order": r.get("order"),
        }
    if parsed.get("action") == "create":
        r = create_order(
            db,
            title=parsed.get("title") or "Auftrag",
            body=parsed.get("body") or text,
            source=source,
            kunde_id=parsed.get("kunde_id"),
            kind=parsed.get("kind") or "general",
            patch=parsed.get("patch"),
            auto_execute=bool(parsed.get("auto_execute")),
        )
        order = r.get("order") or {}
        if r.get("executed"):
            applied = (r.get("result") or {}).get("applied") or []
            bits = []
            for a in applied[:8]:
                if isinstance(a, dict):
                    bits.append(f"{a.get('field')}: {a.get('new') or a.get('value')}")
            reply = (
                f"Erledigt ({order.get('id')}).\n"
                + ("\n".join(bits) if bits else (r.get("text") or "Passt."))
            ).strip()
        else:
            reply = (
                f"Hab den Auftrag angelegt ({order.get('id')}).\n"
                f"{order.get('title')}\n\n"
                f"Das ist ein Cursor-Handoff, kein Auto-Edit. "
                f"Datei: {order.get('handoff_path')}\n"
                f"Liste: /workorders.html"
            )
        return {
            "ok": True,
            "reply": reply[:3900],
            "route": "workorder",
            "order": order,
            "executed": r.get("executed"),
        }
    return None
