# -*- coding: utf-8 -*-
"""Nils Langzeitgedächtnis – hält über Jahre (SQLite), nicht nur Chat-Turns.

Arten:
  preference | fact | person | business | decision | summary | episode

Abruf bei jedem Turn. Extraktion nach wichtigen Turns.
Christian: „merk dir: …“, „vergiss: …“, „gedächtnis“
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
import time
from typing import Any

log = logging.getLogger("telegram_memory")

# Seed nur einmal pro chat_id (Key-basiert)
_SEED_FACTS = (
    ("pref.owner", "preference", 1.0, "Chef ist Christian Kummetat, Mechernich, Webschmiede / Digitale Handwerkskunst."),
    ("pref.tone", "preference", 0.9, "Ton: menschlich, klar, kein Agentur-Sprech. Duzen ok."),
    ("biz.stack", "business", 0.85, "Stack: eigenes CRM (kein GHL), seven.io SMS, n8n, Hetzner, Requesty EU für LLMs."),
    ("biz.client", "business", 0.8, "Erster Live-Kunde: Snack House Yassine (SHY001), Bestellportal."),
    ("pref.money", "preference", 0.95, "Keine Käufe/Domains/Server ohne klares OK. Bezahlte Bilder erst nach Kostenvoranschlag + ja."),
    ("pref.memory", "preference", 0.9, "Gedächtnis soll dauerhaft sein (Jahre), nicht nur Stunden."),
    (
        "biz.tools",
        "business",
        0.95,
        "Nils-Tools live: list_tools, web_context, scrape_website, meeting_scan, register_lookup, "
        "golf_club_text, instagram_caption, draft_document, website_template, send_mail (Freigabe), "
        "send_offer/onboarding, kunden/ops/radar/akquise. Instagram Meta-Upload noch Stub.",
    ),
    (
        "pref.voice_server",
        "preference",
        0.9,
        "Christian will Nils als Stimme zum Server: Telegram steuert Agentur-Werkzeuge.",
    ),
    (
        "biz.cursor_bridge",
        "business",
        0.95,
        "Programmieren/Website unterwegs = Cursor + Freigabe + Auto-Deploy (GITHUB_TOKEN). Mail nur nach Freigabe.",
    ),
    (
        "biz.orchestrator",
        "business",
        0.95,
        "Nils-Orchestrator entscheidet bei Arbeit: Lead, Team, LLM-Route A/B/C, Tools, Cursor, n8n. Smalltalk = Companion.",
    ),
    (
        "pref.truth",
        "preference",
        1.0,
        "Halluzinations-Verbot: Nur belegte Fakten aus Tools/Gedächtnis/Live-Suche. Unbekannt ehrlich sagen.",
    ),
    (
        "pref.inventory",
        "preference",
        1.0,
        "Nils kennt seinen Werkzeugkasten live (inventar) und greift selbst zu. Christian muss Tools nicht nennen.",
    ),
    (
        "pref.discovery_eta",
        "preference",
        1.0,
        "Vor Bau: Discovery (Fragen+Vorschläge), dann Freigabe. Keine Fake-Minuten. Hirn-Wächter/Night-Worker laufen.",
    ),
    (
        "pref.guided_cursor_level",
        "preference",
        1.0,
        "Nils führt Cursor-Level: verstehen, Fragen, Vorschläge, nächster Schritt. Aktion erst nach Freigabe (mach das/ja). Überspringen: ohne fragen.",
    ),
)


def ensure_tables(db: sqlite3.Connection) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS nils_long_memory (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id     TEXT NOT NULL,
            kind        TEXT NOT NULL,
            key         TEXT,
            content     TEXT NOT NULL,
            importance  REAL DEFAULT 0.5,
            source      TEXT DEFAULT 'telegram',
            created_at  REAL,
            updated_at  REAL,
            last_used_at REAL
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_nils_mem_chat ON nils_long_memory(chat_id, importance DESC, updated_at DESC)"
    )
    db.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_nils_mem_chat_key
        ON nils_long_memory(chat_id, key)
        WHERE key IS NOT NULL AND key != ''
        """
    )


def seed_if_empty(db: sqlite3.Connection, chat_id: str) -> None:
    """Seed + fehlende Seed-Keys nachziehen (z. B. neue Tools)."""
    ensure_tables(db)
    cid = str(chat_id)
    now = time.time()
    for key, kind, imp, content in _SEED_FACTS:
        row = db.execute(
            "SELECT id FROM nils_long_memory WHERE chat_id=? AND key=? LIMIT 1",
            (cid, key),
        ).fetchone()
        if row:
            continue
        db.execute(
            """
            INSERT INTO nils_long_memory
            (chat_id, kind, key, content, importance, source, created_at, updated_at, last_used_at)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (cid, kind, key, content, imp, "seed", now, now, now),
        )
    try:
        db.commit()
    except Exception:
        pass


def upsert(
    db: sqlite3.Connection,
    chat_id: str,
    content: str,
    *,
    kind: str = "fact",
    key: str | None = None,
    importance: float = 0.6,
    source: str = "telegram",
) -> dict[str, Any]:
    ensure_tables(db)
    cid = str(chat_id)
    text = (content or "").strip()
    if not text:
        return {"ok": False, "error": "empty"}
    now = time.time()
    imp = max(0.0, min(1.0, float(importance)))
    k = (key or "").strip() or None
    if k:
        row = db.execute(
            "SELECT id, importance FROM nils_long_memory WHERE chat_id=? AND key=?",
            (cid, k),
        ).fetchone()
        if row:
            db.execute(
                """
                UPDATE nils_long_memory
                SET content=?, kind=?, importance=?, source=?, updated_at=?
                WHERE id=?
                """,
                (text[:2000], kind, max(float(row[1] or 0), imp), source, now, row[0]),
            )
        else:
            db.execute(
                """
                INSERT INTO nils_long_memory
                (chat_id, kind, key, content, importance, source, created_at, updated_at, last_used_at)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (cid, kind, k, text[:2000], imp, source, now, now, now),
            )
    else:
        db.execute(
            """
            INSERT INTO nils_long_memory
            (chat_id, kind, key, content, importance, source, created_at, updated_at, last_used_at)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (cid, kind, None, text[:2000], imp, source, now, now, now),
        )
    try:
        db.commit()
    except Exception:
        pass
    return {"ok": True, "key": k, "content": text[:200]}


def forget(db: sqlite3.Connection, chat_id: str, needle: str) -> dict[str, Any]:
    ensure_tables(db)
    cid = str(chat_id)
    n = (needle or "").strip()
    if not n:
        return {"ok": False, "error": "empty"}
    cur = db.execute(
        """
        DELETE FROM nils_long_memory
        WHERE chat_id=? AND (
          key = ? OR content LIKE ? OR id = ?
        )
        """,
        (cid, n, f"%{n}%", int(n) if n.isdigit() else -1),
    )
    deleted = cur.rowcount
    try:
        db.commit()
    except Exception:
        pass
    return {"ok": True, "deleted": deleted}


def list_memory(db: sqlite3.Connection, chat_id: str, *, limit: int = 40) -> list[dict[str, Any]]:
    ensure_tables(db)
    seed_if_empty(db, chat_id)
    rows = db.execute(
        """
        SELECT id, kind, key, content, importance, updated_at
        FROM nils_long_memory
        WHERE chat_id=?
        ORDER BY importance DESC, updated_at DESC
        LIMIT ?
        """,
        (str(chat_id), int(limit)),
    ).fetchall()
    out = []
    for r in rows:
        out.append(
            {
                "id": r[0],
                "kind": r[1],
                "key": r[2],
                "content": r[3],
                "importance": r[4],
                "updated_at": r[5],
            }
        )
    return out


def retrieve(db: sqlite3.Connection, chat_id: str, query: str = "", *, limit: int = 14) -> list[dict[str, Any]]:
    """Relevante Dauer-Fakten für den Prompt. Keyword-Match + Importance."""
    ensure_tables(db)
    seed_if_empty(db, chat_id)
    cid = str(chat_id)
    q = (query or "").lower()
    tokens = [t for t in re.findall(r"[a-zäöüß0-9]{3,}", q) if t not in ("und", "oder", "der", "die", "das", "ich", "du")]
    rows = db.execute(
        """
        SELECT id, kind, key, content, importance, updated_at
        FROM nils_long_memory
        WHERE chat_id=?
        ORDER BY importance DESC, updated_at DESC
        LIMIT 80
        """,
        (cid,),
    ).fetchall()
    scored: list[tuple[float, dict]] = []
    now = time.time()
    for r in rows:
        item = {
            "id": r[0],
            "kind": r[1],
            "key": r[2],
            "content": r[3],
            "importance": float(r[4] or 0.5),
        }
        body = (item["content"] or "").lower()
        score = item["importance"]
        if item["kind"] in ("preference", "business"):
            score += 0.15
        if tokens:
            hits = sum(1 for t in tokens if t in body or t in (item.get("key") or ""))
            score += min(0.5, hits * 0.12)
        else:
            score += 0.05
        # leichte Frische
        age_days = max(0.0, (now - float(r[5] or now)) / 86400.0)
        if age_days < 30:
            score += 0.05
        scored.append((score, item))
    scored.sort(key=lambda x: -x[0])
    picked = [it for _, it in scored[: max(1, int(limit))]]
    # last_used markieren
    ids = [p["id"] for p in picked]
    if ids:
        db.execute(
            f"UPDATE nils_long_memory SET last_used_at=? WHERE id IN ({','.join('?' * len(ids))})",
            [now, *ids],
        )
        try:
            db.commit()
        except Exception:
            pass
    return picked


def format_for_prompt(facts: list[dict[str, Any]]) -> str:
    if not facts:
        return ""
    lines = ["Langzeitgedächtnis (dauerhaft, Jahre – nutzen, nichts erfinden):"]
    for f in facts:
        kind = f.get("kind") or "fact"
        lines.append(f"- [{kind}] {f.get('content')}")
    return "\n".join(lines)[:3500]


def handle_memory_command(db: sqlite3.Connection, chat_id: str, text: str) -> dict[str, Any] | None:
    """Explizite Merk-/Vergiss-/Liste-Befehle. None = kein Memory-Command."""
    t = (text or "").strip()
    low = t.lower()
    if low in ("gedächtnis", "memory", "was weißt du", "was weisst du", "was merkst du dir"):
        items = list_memory(db, chat_id, limit=25)
        if not items:
            return {"reply": "Noch nichts Dauerhaftes gespeichert.", "route": "memory_list"}
        lines = ["Das behalte ich dauerhaft:"]
        for it in items[:20]:
            kid = it.get("id")
            lines.append(f"• #{kid} [{it.get('kind')}] {it.get('content')}")
        lines.append("Vergessen: „vergiss: Stichwort“ oder „vergiss: #id“.")
        return {"reply": "\n".join(lines), "route": "memory_list"}

    m = re.match(r"^(?:merk\s*dir|merke\s*dir|remember)\s*[:\-]?\s*(.+)$", t, re.I | re.S)
    if m:
        content = m.group(1).strip()
        upsert(db, chat_id, content, kind="fact", key=None, importance=0.85, source="explicit")
        return {"reply": f"Merke ich mir dauerhaft: {content[:300]}", "route": "memory_save"}

    m = re.match(r"^(?:vergiss|forget|lösche|loesche)\s*[:\-]?\s*(.+)$", t, re.I | re.S)
    if m:
        needle = m.group(1).strip().lstrip("#")
        r = forget(db, chat_id, needle)
        return {
            "reply": f"Ok, {r.get('deleted', 0)} Einträge dazu gelöscht." if r.get("deleted") else "Nichts Passendes gefunden.",
            "route": "memory_forget",
        }
    return None


def extract_and_store(db: sqlite3.Connection, chat_id: str, user_text: str, assistant_text: str) -> None:
    """Günstiger Extrakt dauerhafter Fakten nach einem Turn (best effort)."""
    u = (user_text or "").strip()
    a = (assistant_text or "").strip()
    if len(u) < 12:
        return
    # Schnellpfad ohne LLM: klare Präferenz-Sätze
    low = u.lower()
    if any(x in low for x in ("immer", "nie", "ab sofort", "merk dir", "ich will", "ich mag", "lieber")):
        if len(u) < 400:
            upsert(db, chat_id, u, kind="preference", importance=0.7, source="heuristic")

    # LLM-Extrakt nur bei Substanz
    if len(u) < 40 and len(a) < 80:
        return
    try:
        import llm_client as llm

        messages = [
            {
                "role": "system",
                "content": (
                    "Extrahiere NUR dauerhaft wichtige Fakten über Christian/Webschmiede "
                    "als JSON-Array: [{\"kind\":\"preference|fact|business|decision|person\","
                    "\"key\":\"optional.stable.key\",\"content\":\"…\",\"importance\":0.0-1.0}]. "
                    "Max 3 Einträge. Leer [] wenn nichts Dauerhaftes. Kein Smalltalk."
                ),
            },
            {
                "role": "user",
                "content": f"Christian:\n{u[:1500]}\n\nNils:\n{a[:1500]}",
            },
        ]
        result = llm.chat(messages, max_tokens=280, temperature=0.1, timeout=25, route="A")
        if not result.get("ok"):
            return
        raw = (result.get("reply") or "").strip()
        start, end = raw.find("["), raw.rfind("]")
        if start < 0 or end <= start:
            return
        data = json.loads(raw[start : end + 1])
        if not isinstance(data, list):
            return
        for item in data[:3]:
            if not isinstance(item, dict):
                continue
            content = (item.get("content") or "").strip()
            if len(content) < 8:
                continue
            upsert(
                db,
                chat_id,
                content,
                kind=str(item.get("kind") or "fact")[:32],
                key=(str(item.get("key") or "").strip() or None),
                importance=float(item.get("importance") or 0.55),
                source="extract",
            )
    except Exception as e:
        log.debug("memory extract skip: %s", e)


def maybe_session_summary(db: sqlite3.Connection, chat_id: str, recent_turns: list[dict]) -> None:
    """Wenn viele Turns: Kurz-Summary dauerhaft ablegen."""
    if len(recent_turns) < 8:
        return
    blob = []
    for t in recent_turns[-10:]:
        role = t.get("role") or "?"
        body = (t.get("body") or "")[:200]
        blob.append(f"{role}: {body}")
    text = "\n".join(blob)
    key = f"summary.{int(time.time() // 86400)}"  # eine Summary pro Tag max upsert
    upsert(
        db,
        chat_id,
        f"Tages-Kontext: {text[:900]}",
        kind="summary",
        key=key,
        importance=0.45,
        source="summary",
    )
