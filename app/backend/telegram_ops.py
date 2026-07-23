"""Telegram Ops: Christian ↔ Nils (intern), unabhängig von Meta/WhatsApp.

Setup: BotFather → Token → TELEGRAM_BOT_TOKEN + TELEGRAM_OWNER_CHAT_ID
Webhook: https://digitalehandwerkskunst.de/api/telegram/webhook

Krisenfest:
- Webhook ACK <100ms + Dedup (Memory 60s + SQLite)
- Session pro chat_id (nur user/assistant)
- Telegram 429/5xx Retry, höfliche User-Fehler
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from typing import Any

import requests

import nils_ops as nils_ops_svc
import telegram_agent as tg_agent
import telegram_session as tg_sess
import agency_workorders as workorders

log = logging.getLogger("telegram_ops")

TG_API = "https://api.telegram.org/bot{token}"
USER_SOFT_ERROR = tg_sess.USER_SOFT_ERROR


def bot_token() -> str:
    return (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()


def owner_chat_ids() -> list[str]:
    raw = (
        os.getenv("TELEGRAM_OWNER_CHAT_ID")
        or os.getenv("TELEGRAM_OWNER_CHAT_IDS")
        or os.getenv("NILS_TELEGRAM_CHAT_IDS")
        or ""
    )
    parts = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
    # Nur Ziffern / negative IDs (Gruppen)
    out: list[str] = []
    for p in parts:
        if p.lstrip("-").isdigit():
            out.append(p)
    return out


def is_owner_chat(chat_id: str | int) -> bool:
    cid = str(chat_id or "").strip()
    if not cid:
        return False
    owners = owner_chat_ids()
    if not owners:
        # Erster Kontakt: erlauben und Chat-ID in Antwort nennen (Bootstrap)
        return True
    return cid in owners


def webhook_secret() -> str:
    return (os.getenv("TELEGRAM_WEBHOOK_SECRET") or "").strip()


def readiness() -> dict[str, Any]:
    token = bool(bot_token())
    owners = owner_chat_ids()
    return {
        "ok": token and bool(owners),
        "agent": "nils",
        "channel": "telegram_ops",
        "bot_token": token,
        "owner_chats": len(owners),
        "owner_chats_masked": [f"…{c[-4:]}" if len(c) > 4 else c for c in owners],
        "webhook": "https://digitalehandwerkskunst.de/api/telegram/webhook",
        "next_steps": _next_steps(token, owners),
        "note": "Intern Christian↔Nils. Kein Kundenkanal. Kunden = WhatsApp.",
    }


def _next_steps(token: bool, owners: list[str]) -> list[str]:
    steps = []
    if not token:
        steps.append("Bei @BotFather /newbot → Token in Agency-Setup (TELEGRAM_BOT_TOKEN)")
    if not owners:
        steps.append("Bot anschreiben, /start → Chat-ID kommt in der Antwort → TELEGRAM_OWNER_CHAT_ID setzen")
    if token and owners:
        steps.append("„Nils Status“ an den Bot schreiben")
    else:
        steps.append("Webhook setzen: python scripts/setup_telegram_webhook.py")
    return steps


def send_chat_action(chat_id: str | int, action: str = "typing") -> None:
    token = bot_token()
    cid = str(chat_id or "").strip()
    if not token or not cid:
        return
    try:
        requests.post(
            f"{TG_API.format(token=token)}/sendChatAction",
            json={"chat_id": cid, "action": action},
            timeout=2,
        )
    except Exception as e:
        log.debug("sendChatAction fail: %s", e)


def _tg_api(
    method: str,
    *,
    json_body: dict | None = None,
    data: dict | None = None,
    files: dict | None = None,
    timeout: float = 30,
    retries: int = 3,
) -> dict[str, Any]:
    """Telegram API mit 429/5xx-Backoff. Nie ungefangen crashen lassen."""
    token = bot_token()
    if not token:
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN fehlt"}
    url = f"{TG_API.format(token=token)}/{method}"
    last: dict[str, Any] = {"ok": False, "error": "no_attempt"}
    for attempt in range(max(1, retries)):
        try:
            if files:
                r = requests.post(url, data=data or {}, files=files, timeout=timeout)
            else:
                r = requests.post(url, json=json_body or data or {}, timeout=timeout)
            try:
                last = r.json() if r.content else {"ok": r.ok}
            except Exception:
                last = {"ok": r.ok, "error": f"http_{r.status_code}"}
            if r.status_code == 429 or (isinstance(last, dict) and last.get("error_code") == 429):
                wait = 1.0
                try:
                    wait = float((last.get("parameters") or {}).get("retry_after") or 1)
                except Exception:
                    wait = 1.0 + attempt
                wait = min(max(wait, 0.5), 8.0)
                log.warning("Telegram 429 %s, wait %.1fs (attempt %s)", method, wait, attempt + 1)
                time.sleep(wait)
                continue
            if r.status_code >= 500:
                log.warning("Telegram %s http_%s attempt %s", method, r.status_code, attempt + 1)
                time.sleep(0.6 * (attempt + 1))
                continue
            if not r.ok:
                return {
                    "ok": False,
                    "error": f"http_{r.status_code}",
                    "channel": "telegram",
                    "telegram": last,
                }
            return {"ok": bool(last.get("ok", True)), "channel": "telegram", "telegram": last}
        except requests.Timeout as e:
            log.warning("Telegram timeout %s: %s", method, e)
            last = {"ok": False, "error": "timeout"}
            time.sleep(0.4 * (attempt + 1))
        except Exception as e:
            log.exception("Telegram API %s", method)
            return {"ok": False, "error": str(e)[:160], "channel": "telegram"}
    return {"ok": False, "error": last.get("error") or "retries_exhausted", "channel": "telegram", "telegram": last}


def send_message(chat_id: str | int, text: str) -> dict[str, Any]:
    token = bot_token()
    if not token:
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN fehlt", "channel": "telegram"}
    cid = str(chat_id or "").strip()
    if not cid:
        return {"ok": False, "error": "chat_id fehlt", "channel": "telegram"}
    full = (text or "").strip() or "…"
    try:
        import nils_eta as eta

        full = eta.strip_fake_etas(full) or full
    except Exception:
        pass
    # Telegram Limit ~4096; längere Antworten in Chunks
    chunks: list[str] = []
    rest = full
    while rest:
        if len(rest) <= 3900:
            chunks.append(rest)
            break
        cut = rest.rfind("\n", 0, 3900)
        if cut < 800:
            cut = 3900
        chunks.append(rest[:cut])
        rest = rest[cut:].lstrip()
    last: dict[str, Any] = {"ok": False}
    for chunk in chunks:
        last = _tg_api(
            "sendMessage",
            json_body={"chat_id": cid, "text": chunk},
            timeout=30,
            retries=3,
        )
        if not last.get("ok"):
            return last
    return last


def send_photo(chat_id: str | int, path: str, *, caption: str = "") -> dict[str, Any]:
    token = bot_token()
    if not token:
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN fehlt", "channel": "telegram"}
    cid = str(chat_id or "").strip()
    from pathlib import Path

    p = Path(path)
    if not cid or not p.is_file():
        return {"ok": False, "error": "chat_or_file_missing", "channel": "telegram"}
    try:
        with p.open("rb") as f:
            return _tg_api(
                "sendPhoto",
                data={"chat_id": cid, "caption": (caption or "")[:900]},
                files={"photo": (p.name, f, "image/png")},
                timeout=60,
                retries=2,
            )
    except Exception as e:
        log.exception("send_photo")
        return {"ok": False, "error": str(e)[:160], "channel": "telegram"}


def notify_soft_error(chat_id: str | int, *, detail: str = "") -> None:
    """Höfliche User-Meldung + detailliertes Log."""
    if detail:
        log.error("Nils Telegram soft-error chat=%s detail=%s", chat_id, detail[:400])
    try:
        send_message(chat_id, USER_SOFT_ERROR)
    except Exception:
        log.exception("soft_error_notify_failed")


def _stream_interval_ms() -> int:
    try:
        return max(200, min(int(os.getenv("NILS_TG_STREAM_MS", "300") or 300), 2000))
    except Exception:
        return 300


def stream_enabled() -> bool:
    # Default AUS: editMessageText-Roundtrips machen kurze Antworten langsamer.
    try:
        import llm_client as llm

        raw = llm._env("NILS_TG_STREAM", "0")
    except Exception:
        raw = os.getenv("NILS_TG_STREAM", "0") or "0"
    return raw.strip().lower() not in ("0", "false", "no", "")


def send_fast_llm(
    chat_id: str | int,
    messages: list[dict],
    *,
    max_tokens: int = 900,
    temperature: float = 0.65,
) -> dict[str, Any]:
    """Telegram-Pfad: Typing → 1× Requesty → 1× sendMessage.

    Tokens bewusst höher als früher (280), sonst kommen nur Satzfetzen.
    """
    import time

    import llm_client as llm

    cid = str(chat_id or "").strip()
    token = bot_token()
    if not token or not cid:
        return {"ok": False, "error": "token_or_chat_missing"}

    send_chat_action(cid, "typing")

    model = (
        llm._env("REQUESTY_CHAT_MODEL")
        or llm._env("NILS_TG_FAST_MODEL")
        or "mistral/mistral-small-latest"
    )
    t0 = time.perf_counter()
    result = llm._chat_openai_compatible(
        messages,
        base_url=llm.primary_gateway_url(),
        key=llm.primary_api_key(),
        model=model,
        provider="primary",
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=35,
    )
    if not (result.get("ok") and result.get("reply")):
        # Ein Fallback-Modell, dann fertig
        result = llm._chat_openai_compatible(
            messages,
            base_url=llm.primary_gateway_url(),
            key=llm.primary_api_key(),
            model="azure/gpt-4o-mini@swedencentral",
            provider="primary",
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=35,
        )

    reply = (result.get("reply") or USER_SOFT_ERROR).strip()
    sent = send_message(cid, reply)
    if not sent.get("ok"):
        log.error("send_fast_llm send fail: %s", sent.get("error"))
        notify_soft_error(cid, detail=str(sent.get("error") or "send_fail"))
    return {
        "ok": bool(result.get("ok")) and bool(sent.get("ok")),
        "reply": reply,
        "streamed": False,
        "fast": True,
        "ms": int((time.perf_counter() - t0) * 1000),
        "model": result.get("model") or model,
        "provider": result.get("provider") or "primary",
        "error": result.get("error") or sent.get("error"),
    }


def send_streaming_llm(
    chat_id: str | int,
    messages: list[dict],
    *,
    route: str = "A",
    max_tokens: int = 450,
    temperature: float = 0.7,
) -> dict[str, Any]:
    """Optional Streaming. Standard: send_fast_llm (schneller)."""
    if not stream_enabled():
        return send_fast_llm(chat_id, messages, max_tokens=max(max_tokens, 700), temperature=temperature)

    import time

    import nils_dispatcher as disp

    cid = str(chat_id or "").strip()
    token = bot_token()
    if not token or not cid:
        return {"ok": False, "error": "token_or_chat_missing"}

    try:
        requests.post(
            f"{TG_API.format(token=token)}/sendChatAction",
            json={"chat_id": cid, "action": "typing"},
            timeout=2,
        )
    except Exception:
        pass

    placeholder = requests.post(
        f"{TG_API.format(token=token)}/sendMessage",
        json={"chat_id": cid, "text": "…", "disable_web_page_preview": True},
        timeout=12,
    )
    pdata = placeholder.json() if placeholder.content else {}
    msg_id = ((pdata.get("result") or {}).get("message_id")) if pdata.get("ok") else None

    state = {"text": "", "last": 0.0, "words": 0, "edits": 0}

    def _edit(force: bool = False) -> None:
        if not msg_id:
            return
        now = time.time()
        words = len(state["text"].split())
        interval = _stream_interval_ms() / 1000.0
        if not force and (now - state["last"]) < interval and (words - state["words"]) < 8:
            return
        body = (state["text"] or "…").strip()[:3900] or "…"
        try:
            requests.post(
                f"{TG_API.format(token=token)}/editMessageText",
                json={"chat_id": cid, "message_id": msg_id, "text": body, "disable_web_page_preview": True},
                timeout=4,
            )
            state["last"] = now
            state["words"] = words
            state["edits"] += 1
        except Exception:
            pass

    def on_delta(delta: str) -> None:
        state["text"] += delta
        _edit(False)

    result = disp.dispatch_stream(
        messages,
        route=route,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=40,
        on_delta=on_delta if msg_id else None,
    )
    if result.get("ok") and result.get("reply"):
        state["text"] = result["reply"]
        _edit(True)
        if not msg_id:
            send_message(cid, result["reply"])
        return {
            "ok": True,
            "reply": result["reply"],
            "streamed": bool(result.get("streamed")),
            "edits": state["edits"],
            "route": result.get("route"),
            "model": result.get("model"),
            "provider": result.get("provider"),
        }

    reply = (result.get("reply") or "Kurz hängt mein Hirn. Versuch in einer Minute nochmal.").strip()
    if msg_id:
        state["text"] = reply
        _edit(True)
    else:
        send_message(cid, reply)
    return {"ok": bool(result.get("ok")), "reply": reply, "streamed": False, "error": result.get("error")}


def notify_owner(text: str) -> dict[str, Any]:
    """Funnel/Ops-Ping an alle Owner-Chats."""
    owners = owner_chat_ids()
    if not owners:
        return {"ok": False, "skipped": True, "detail": "TELEGRAM_OWNER_CHAT_ID fehlt"}
    results = []
    ok_any = False
    for cid in owners:
        r = send_message(cid, text)
        results.append(r)
        ok_any = ok_any or bool(r.get("ok"))
    return {"ok": ok_any, "channel": "telegram", "results": results}


def ensure_sessions(db: sqlite3.Connection) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS nils_tg_sessions (
            chat_id    TEXT PRIMARY KEY,
            pending    TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS telegram_updates (
            update_id   INTEGER PRIMARY KEY,
            chat_id     TEXT,
            message_id  INTEGER,
            status      TEXT,
            created_at  REAL,
            finished_at REAL
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS telegram_chat_locks (
            chat_id   TEXT PRIMARY KEY,
            update_id INTEGER,
            locked_at REAL
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS telegram_chat_turns (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id    TEXT NOT NULL,
            role       TEXT NOT NULL,
            body       TEXT NOT NULL,
            created_at REAL
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_tg_turns_chat ON telegram_chat_turns(chat_id, id)"
    )


def _persist_turn(db: sqlite3.Connection, chat_id: str, role: str, body: str) -> None:
    """Memory + SQLite, strikt user|assistant."""
    tg_sess.append_turn(chat_id, role, body)
    r = (role or "").lower()
    if r not in ("user", "assistant"):
        return
    text = (body or "").strip()
    if not text:
        return
    ensure_sessions(db)
    db.execute(
        "INSERT INTO telegram_chat_turns (chat_id, role, body, created_at) VALUES (?,?,?,?)",
        (str(chat_id), r, text[:4000], time.time()),
    )
    # Alte Turns trimmen (pro Chat max 40)
    db.execute(
        """
        DELETE FROM telegram_chat_turns WHERE chat_id=? AND id NOT IN (
          SELECT id FROM telegram_chat_turns WHERE chat_id=? ORDER BY id DESC LIMIT 40
        )
        """,
        (str(chat_id), str(chat_id)),
    )


def _load_chat_history(db: sqlite3.Connection, chat_id: str, limit: int = 6) -> list[dict]:
    """Nur dieser chat_id. Memory zuerst, sonst SQLite."""
    mem = tg_sess.get_turns(chat_id, limit=limit)
    if mem:
        return mem
    ensure_sessions(db)
    rows = db.execute(
        """
        SELECT role, body FROM telegram_chat_turns
        WHERE chat_id=? ORDER BY id DESC LIMIT ?
        """,
        (str(chat_id), int(limit)),
    ).fetchall()
    out = []
    for r in reversed(rows):
        role = r[0] if not isinstance(r, sqlite3.Row) else r["role"]
        body = r[1] if not isinstance(r, sqlite3.Row) else r["body"]
        if role in ("user", "assistant") and body:
            out.append({"role": role, "body": body})
            tg_sess.append_turn(chat_id, role, body)
    return out


def claim_update(
    db: sqlite3.Connection,
    update_id: int | None,
    *,
    chat_id: str = "",
    message_id: int = 0,
) -> bool:
    """True = diese Instanz darf verarbeiten. False = Duplikat/Retry von Telegram."""
    # Schneller In-Memory-Cache (60s) – greift auch über Worker hinweg im gleichen Prozess
    if not tg_sess.remember_incoming(
        update_id=update_id if update_id is not None else None,
        chat_id=chat_id,
        message_id=message_id or None,
    ):
        return False

    if update_id is None:
        # Ohne update_id: Memory-Dedup über message_id reicht; SQLite-PK fehlt
        return bool(message_id and chat_id)

    ensure_sessions(db)
    now = time.time()
    uid = int(update_id)
    try:
        db.execute(
            """INSERT INTO telegram_updates
               (update_id, chat_id, message_id, status, created_at)
               VALUES (?,?,?,?,?)""",
            (uid, str(chat_id or ""), int(message_id or 0), "processing", now),
        )
        db.commit()
        return True
    except sqlite3.IntegrityError:
        row = db.execute(
            "SELECT status, created_at FROM telegram_updates WHERE update_id=?",
            (uid,),
        ).fetchone()
        if not row:
            return False
        status = row[0] if not isinstance(row, sqlite3.Row) else row["status"]
        created = float(row[1] if not isinstance(row, sqlite3.Row) else row["created_at"] or 0)
        # Schon fertig oder noch in Arbeit → Retry ignorieren
        if status in ("done", "processing", "error", "skipped_busy") and (now - created) < 300:
            return False
        # Verwaist (>5 Min) → neu claimen
        db.execute(
            "UPDATE telegram_updates SET status=?, created_at=?, finished_at=NULL WHERE update_id=?",
            ("processing", now, uid),
        )
        db.commit()
        return True
    except Exception as e:
        log.exception("claim_update: %s", e)
        return False


def finish_update(db: sqlite3.Connection, update_id: int | None, status: str = "done") -> None:
    if update_id is None:
        return
    ensure_sessions(db)
    db.execute(
        "UPDATE telegram_updates SET status=?, finished_at=? WHERE update_id=?",
        (status, time.time(), int(update_id)),
    )
    try:
        db.commit()
    except Exception:
        pass


def claim_chat_lock(db: sqlite3.Connection, chat_id: str, update_id: int | None) -> bool:
    """Ein Chat = eine laufende Antwort. Verhindert parallele Doppel-Antworten."""
    ensure_sessions(db)
    now = time.time()
    cid = str(chat_id or "")
    row = db.execute(
        "SELECT update_id, locked_at FROM telegram_chat_locks WHERE chat_id=?",
        (cid,),
    ).fetchone()
    if row:
        locked_at = float(row[1] if not isinstance(row, sqlite3.Row) else row["locked_at"] or 0)
        if (now - locked_at) < 120:
            return False
    db.execute(
        """INSERT INTO telegram_chat_locks (chat_id, update_id, locked_at) VALUES (?,?,?)
           ON CONFLICT(chat_id) DO UPDATE SET update_id=excluded.update_id, locked_at=excluded.locked_at""",
        (cid, int(update_id or 0), now),
    )
    try:
        db.commit()
    except Exception:
        pass
    return True


def release_chat_lock(db: sqlite3.Connection, chat_id: str, update_id: int | None = None) -> None:
    ensure_sessions(db)
    cid = str(chat_id or "")
    if update_id is not None:
        db.execute(
            "DELETE FROM telegram_chat_locks WHERE chat_id=? AND update_id=?",
            (cid, int(update_id)),
        )
    else:
        db.execute("DELETE FROM telegram_chat_locks WHERE chat_id=?", (cid,))
    try:
        db.commit()
    except Exception:
        pass


def _get_pending(db: sqlite3.Connection, chat_id: str) -> dict | None:
    ensure_sessions(db)
    row = db.execute(
        "SELECT pending FROM nils_tg_sessions WHERE chat_id=?",
        (str(chat_id),),
    ).fetchone()
    if not row or not row[0]:
        return None
    try:
        return json.loads(row[0])
    except Exception:
        return None


def _set_pending(db: sqlite3.Connection, chat_id: str, pending: dict | None) -> None:
    ensure_sessions(db)
    cid = str(chat_id)
    if pending is None:
        db.execute("DELETE FROM nils_tg_sessions WHERE chat_id=?", (cid,))
        return
    db.execute(
        """
        INSERT INTO nils_tg_sessions (chat_id, pending, updated_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(chat_id) DO UPDATE SET
          pending=excluded.pending,
          updated_at=datetime('now')
        """,
        (cid, json.dumps(pending, ensure_ascii=False)),
    )


def parse_update(payload: dict[str, Any]) -> dict[str, Any] | None:
    msg = payload.get("message") or payload.get("edited_message")
    if not isinstance(msg, dict):
        return None
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    text = (msg.get("text") or msg.get("caption") or "").strip()
    from_user = msg.get("from") or {}
    if chat_id is None:
        return None
    voice = msg.get("voice") or msg.get("audio") or None
    # Größtes Foto (Telegram liefert sizes[])
    photo = None
    photos = msg.get("photo")
    if isinstance(photos, list) and photos:
        photo = photos[-1] if isinstance(photos[-1], dict) else None
    document = msg.get("document") if isinstance(msg.get("document"), dict) else None
    return {
        "chat_id": str(chat_id),
        "text": text,
        "username": from_user.get("username") or "",
        "first_name": from_user.get("first_name") or "",
        "message_id": msg.get("message_id"),
        "update_id": payload.get("update_id"),
        "voice": voice if isinstance(voice, dict) else None,
        "photo": photo,
        "document": document,
    }


def _download_telegram_file(file_id: str) -> dict[str, Any]:
    """Telegram-Datei laden → lokaler Temp-Pfad."""
    import tempfile
    from pathlib import Path

    token = bot_token()
    if not token or not file_id:
        return {"ok": False, "error": "token_or_file_missing"}
    try:
        meta = requests.get(
            f"{TG_API.format(token=token)}/getFile",
            params={"file_id": file_id},
            timeout=20,
        )
        if not meta.ok:
            return {"ok": False, "error": f"getFile_{meta.status_code}"}
        file_path = ((meta.json().get("result") or {}).get("file_path") or "").strip()
        if not file_path:
            return {"ok": False, "error": "no_file_path"}
        url = f"https://api.telegram.org/file/bot{token}/{file_path}"
        r = requests.get(url, timeout=60)
        if not r.ok:
            return {"ok": False, "error": f"download_{r.status_code}"}
        suffix = Path(file_path).suffix or ".ogg"
        fd, tmp = tempfile.mkstemp(suffix=suffix, prefix="tg_voice_")
        Path(tmp).write_bytes(r.content)
        try:
            import os as _os

            _os.close(fd)
        except Exception:
            pass
        return {"ok": True, "path": tmp, "bytes": len(r.content)}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}"}


def _voice_to_text(voice: dict[str, Any]) -> dict[str, Any]:
    import llm_client as llm

    file_id = (voice or {}).get("file_id") or ""
    dl = _download_telegram_file(file_id)
    if not dl.get("ok"):
        return {"ok": False, "error": dl.get("error") or "download_failed"}
    path = dl["path"]
    try:
        stt = llm.transcribe_audio_file(path, language="de")
        return stt
    finally:
        try:
            from pathlib import Path

            Path(path).unlink(missing_ok=True)
        except Exception:
            pass


def _media_to_notes(parsed: dict[str, Any], caption: str = "") -> list[str]:
    """Foto/PDF/Dokument → Textnotizen fürs LLM (Vision / PDF-Text)."""
    notes: list[str] = []
    from pathlib import Path

    photo = parsed.get("photo")
    if isinstance(photo, dict) and photo.get("file_id"):
        send_chat_action(parsed.get("chat_id") or "", "upload_photo")
        dl = _download_telegram_file(photo["file_id"])
        if dl.get("ok"):
            path = dl["path"]
            try:
                import requesty_client as rq

                prompt = (
                    "Beschreibe dieses Bild für Christian (Webschmiede). "
                    "Was ist drauf, Texte lesen, was er vermutlich will. Deutsch, klar."
                )
                if caption:
                    prompt += f" Caption/Frage von Christian: {caption[:500]}"
                vis = rq.vision_describe(path, prompt=prompt, timeout=70)
                if vis.get("ok") and vis.get("text"):
                    notes.append(f"Bildanalyse:\n{vis['text']}")
                else:
                    notes.append(f"Bild empfangen, Analyse fehlgeschlagen ({vis.get('error')}).")
            finally:
                try:
                    Path(path).unlink(missing_ok=True)
                except Exception:
                    pass
        else:
            notes.append("Bild konnte nicht geladen werden.")

    doc = parsed.get("document")
    if isinstance(doc, dict) and doc.get("file_id"):
        name = (doc.get("file_name") or "dokument").strip()
        mime = (doc.get("mime_type") or "").lower()
        send_chat_action(parsed.get("chat_id") or "", "typing")
        dl = _download_telegram_file(doc["file_id"])
        if not dl.get("ok"):
            notes.append(f"Dokument {name} konnte nicht geladen werden.")
            return notes
        path = dl["path"]
        try:
            if "pdf" in mime or name.lower().endswith(".pdf"):
                text = _pdf_extract_text(path)
                if text:
                    notes.append(f"PDF „{name}“ (Auszug):\n{text[:3500]}")
                else:
                    notes.append(
                        f"PDF „{name}“ empfangen, Text nicht lesbar (Scan?). "
                        "Schick Seite als Foto, dann lese ich per Vision."
                    )
            elif mime.startswith("image/") or name.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                import requesty_client as rq

                vis = rq.vision_describe(
                    path,
                    prompt=(
                        "Dokument/Bild für Christian beschreiben und Texte lesen. Deutsch."
                        + (f" Frage: {caption[:400]}" if caption else "")
                    ),
                )
                if vis.get("ok"):
                    notes.append(f"Datei „{name}“:\n{vis.get('text')}")
                else:
                    notes.append(f"Bilddatei „{name}“ empfangen, Analyse fail.")
            else:
                notes.append(f"Datei „{name}“ ({mime or 'unbekannt'}) empfangen. "
                             "PDF und Bilder kann ich lesen, andere Typen noch eingeschränkt.")
        finally:
            try:
                Path(path).unlink(missing_ok=True)
            except Exception:
                pass
    return notes


def _pdf_extract_text(path: str) -> str:
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(path)
        parts = []
        for page in reader.pages[:8]:
            parts.append(page.extract_text() or "")
        return "\n".join(parts).strip()
    except Exception:
        pass
    try:
        from PyPDF2 import PdfReader  # type: ignore

        reader = PdfReader(path)
        parts = []
        for page in reader.pages[:8]:
            parts.append(page.extract_text() or "")
        return "\n".join(parts).strip()
    except Exception:
        return ""


def handle_update(
    db: sqlite3.Connection,
    payload: dict[str, Any],
    *,
    already_claimed: bool = False,
) -> dict[str, Any]:
    parsed = parse_update(payload)
    if not parsed:
        return {"ok": True, "ignored": True}
    chat_id = parsed["chat_id"]
    text = parsed["text"]
    update_id = parsed.get("update_id")
    owners = owner_chat_ids()
    status = "done"

    if not already_claimed and not claim_update(
        db,
        update_id,
        chat_id=chat_id,
        message_id=int(parsed.get("message_id") or 0),
    ):
        return {"ok": True, "duplicate": True, "update_id": update_id}

    if not claim_chat_lock(db, chat_id, update_id):
        if tg_sess.should_send_busy_notice(chat_id):
            try:
                send_message(chat_id, tg_sess.BUSY_NOTICE)
            except Exception:
                pass
        finish_update(db, update_id, "skipped_busy")
        return {"ok": True, "busy": True, "update_id": update_id}

    try:
        return _handle_update_inner(db, parsed, text, chat_id, owners)
    except Exception as e:
        status = "error"
        log.exception("handle_update failed update_id=%s", update_id)
        notify_soft_error(chat_id, detail=str(e))
        return {"ok": False, "error": str(e)[:160], "update_id": update_id}
    finally:
        release_chat_lock(db, chat_id, update_id)
        finish_update(db, update_id, status)


def _handle_update_inner(
    db: sqlite3.Connection,
    parsed: dict[str, Any],
    text: str,
    chat_id: str,
    owners: list[str],
) -> dict[str, Any]:
    if not owners:
        reply = (
            f"Hey, Nils hier. Deine Chat-ID ist {chat_id}. "
            "Trag die bitte unter TELEGRAM_OWNER_CHAT_ID im Agency-Setup ein, "
            "dann antworte ich nur noch dir."
        )
        send_message(chat_id, reply)
        return {"ok": True, "bootstrap": True, "chat_id": chat_id}

    if not is_owner_chat(chat_id):
        send_message(
            chat_id,
            "Hey, das ist nur unser interner Ops-Chat. "
            "Als Kunde bitte über die Website oder WhatsApp Business vom Laden.",
        )
        return {"ok": True, "rejected": True}

    voice_meta = None
    if parsed.get("voice") and not text:
        send_chat_action(chat_id, "record_voice")
        send_chat_action(chat_id, "typing")
        try:
            stt = _voice_to_text(parsed["voice"])
        except Exception as e:
            log.exception("voice_stt")
            notify_soft_error(chat_id, detail=f"stt:{e}")
            return {"ok": False, "route": "voice_stt_fail", "error": str(e)[:160]}
        if not stt.get("ok") or not stt.get("text"):
            send_message(
                chat_id,
                "Die Sprachnachricht hab ich nicht verstanden. "
                "Schick nochmal oder schreib kurz als Text.",
            )
            return {"ok": False, "route": "voice_stt_fail", "error": stt.get("error")}
        text = stt["text"]
        voice_meta = {"stt_provider": stt.get("provider"), "transcript": text}
        send_chat_action(chat_id, "typing")

    # Foto / PDF / Dokument
    media_notes: list[str] = []
    if parsed.get("photo") or parsed.get("document"):
        try:
            media_notes = _media_to_notes(parsed, caption=text or "")
        except Exception as e:
            log.exception("media_notes")
            media_notes = [f"Medien-Fehler: {e}"]

    tnorm = (text or "").lower().strip()
    if tnorm in ("/start", "start", "hi", "hallo", "hey") and not media_notes:
        send_message(
            chat_id,
            "Hey Christian, Nils hier. Schreib oder sprich einfach normal.\n\n"
            "Wetter, Ideen, Business, Status SHY001, Alle Kunden, "
            "Fotos/PDFs schicken zum Lesen. "
            "Dauerhaft merken: „merk dir: …“, Übersicht: „gedächtnis“. "
            "Für Stefan: stefan: und deine Frage. "
            "Kunden-Mails erst nach deinem ja.",
        )
        return {"ok": True, "route": "hello"}

    if not (text or "").strip() and not media_notes:
        send_message(chat_id, "Schick Text, Sprachnachricht, Foto oder PDF.")
        return {"ok": True, "route": "empty"}

    # Langzeitgedächtnis-Befehle
    try:
        import telegram_memory as tg_mem

        mem_cmd = tg_mem.handle_memory_command(db, chat_id, text or "")
        if mem_cmd and mem_cmd.get("reply"):
            send_message(chat_id, mem_cmd["reply"])
            return {"ok": True, "route": mem_cmd.get("route") or "memory"}
    except Exception:
        log.exception("memory_cmd")

    pending = _get_pending(db, chat_id)
    history = _load_chat_history(db, chat_id, limit=12)
    send_chat_action(chat_id, "typing")

    # Dauerhaftes Gedächtnis + Live-Fakten in den Agent-Kontext
    memory_block = ""
    try:
        import telegram_memory as tg_mem

        facts = tg_mem.retrieve(db, chat_id, text or "", limit=14)
        memory_block = tg_mem.format_for_prompt(facts)
    except Exception:
        log.exception("memory_retrieve")

    if media_notes and not (text or "").strip():
        text = "Was siehst du / was soll ich damit machen?"

    def _remember(user_text: str, assistant_text: str, meta: dict | None = None) -> None:
        try:
            _persist_turn(db, chat_id, "user", user_text or "")
            _persist_turn(db, chat_id, "assistant", (assistant_text or "")[:4000])
            nils_ops_svc.log_message(
                db,
                role="user",
                body=user_text or "",
                meta={"channel": "telegram", "chat_id": chat_id, **(meta or {})},
            )
            nils_ops_svc.log_message(
                db,
                role="assistant",
                body=(assistant_text or "")[:4000],
                meta={"channel": "telegram", "chat_id": chat_id, **(meta or {})},
            )
            import telegram_memory as tg_mem

            tg_mem.extract_and_store(db, chat_id, user_text or "", assistant_text or "")
            tg_mem.maybe_session_summary(db, chat_id, history)
        except Exception:
            log.exception("remember_turn")

    if not pending:
        wo = workorders.handle_message(db, text or "", source="telegram")
        if wo is not None:
            reply = (wo.get("reply") or "Auftrag verarbeitet.")[:3900]
            _remember(
                text or "",
                reply,
                {
                    "route": wo.get("route"),
                    "order": (wo.get("order") or {}).get("id"),
                    **(voice_meta or {}),
                },
            )
            send_message(chat_id, reply)
            return {
                "ok": bool(wo.get("ok", True)),
                "route": wo.get("route") or "workorder",
                "executed": wo.get("executed"),
                "order_id": (wo.get("order") or {}).get("id"),
            }

    try:
        result = tg_agent.handle(
            db,
            text or "",
            history=history,
            pending=pending,
            from_voice=bool(voice_meta),
            media_notes=media_notes,
            memory_block=memory_block,
        )
    except Exception as e:
        log.exception("tg_agent.handle")
        notify_soft_error(chat_id, detail=str(e))
        return {"ok": False, "route": "agent_error", "error": str(e)[:160]}

    if result.get("stream_messages") and not result.get("generated"):
        streamed = send_streaming_llm(
            chat_id,
            result["stream_messages"],
            route="A",
            max_tokens=900,
            temperature=0.65,
        )
        result["reply"] = streamed.get("reply") or result.get("reply") or ""
        result["streamed"] = streamed.get("streamed")
        result["llm_model"] = streamed.get("model")
        result["llm_provider"] = streamed.get("provider")
        _remember(
            text or "",
            result.get("reply") or "",
            {
                "route": result.get("route"),
                "fast": True,
                "model": streamed.get("model"),
                "ms": streamed.get("ms"),
                **(voice_meta or {}),
            },
        )
        if result.get("pending"):
            _set_pending(db, chat_id, result["pending"])
        elif not result.get("needs_confirm"):
            _set_pending(db, chat_id, None)
        return {
            "ok": bool(streamed.get("ok", True)),
            "route": result.get("route") or "companion",
            "tools": result.get("tools"),
            "streamed": False,
            "voice": bool(voice_meta),
        }

    _remember(
        text or "",
        result.get("reply") or result.get("error") or "",
        {"route": result.get("route"), "tools": result.get("tools"), **(voice_meta or {})},
    )

    if result.get("pending"):
        _set_pending(db, chat_id, result["pending"])
    elif not result.get("needs_confirm"):
        _set_pending(db, chat_id, None)

    reply = (result.get("reply") or result.get("error") or "").strip()
    if not reply:
        reply = "Verstanden. Mehr Details schicken."
    try:
        import nils_ux_gate as ux

        reply = ux.soft_warn_if_done_without_gate(reply)
        result["reply"] = reply
    except Exception:
        pass

    sent_photo = False
    try:
        for item in result.get("generated") or []:
            path = (item or {}).get("path") or ""
            if path:
                cap = reply if not sent_photo else ""
                ph = send_photo(chat_id, path, caption=cap if len(cap) <= 900 else cap[:897] + "…")
                if ph.get("ok"):
                    sent_photo = True
        if not sent_photo:
            sent = send_message(chat_id, reply)
            if not sent.get("ok"):
                notify_soft_error(chat_id, detail=str(sent.get("error") or "send_fail"))
    except Exception as e:
        log.exception("send_reply")
        notify_soft_error(chat_id, detail=str(e))
        return {"ok": False, "error": str(e)[:160]}

    return {
        "ok": True,
        "route": result.get("route") or "agent",
        "tools": result.get("tools"),
        "needs_confirm": result.get("needs_confirm"),
        "force_agent": result.get("force_agent"),
        "voice": bool(voice_meta),
        "photo": sent_photo,
    }


def set_webhook(public_url: str | None = None) -> dict[str, Any]:
    token = bot_token()
    if not token:
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN fehlt"}
    url = (public_url or "https://digitalehandwerkskunst.de/api/telegram/webhook").rstrip("/")
    secret = webhook_secret()
    payload: dict[str, Any] = {
        "url": url,
        "allowed_updates": ["message", "edited_message"],
        "drop_pending_updates": True,
    }
    if secret:
        payload["secret_token"] = secret
    try:
        r = requests.post(
            f"{TG_API.format(token=token)}/setWebhook",
            json=payload,
            timeout=20,
        )
        data = r.json() if r.content else {}
        return {"ok": bool(data.get("ok")), "url": url, "telegram": data}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}
