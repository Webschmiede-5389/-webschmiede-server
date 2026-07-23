"""Telegram Session-Isolation + In-Memory Dedup für Nils.

- Dedup: update_id / chat_id+message_id innerhalb 60s
- History: strikt pro chat_id, nur user|assistant
- Kein Portal-/Stefan-Leak aus nils_ops_log
"""
from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from typing import Any

log = logging.getLogger("telegram_session")

DEDUP_TTL_SEC = 60.0
HISTORY_MAX_TURNS = 16
BUSY_NOTICE_TTL = 45.0

USER_SOFT_ERROR = (
    "Entschuldige Christian, da gab es eine kurze Verbindungsstörung. "
    "Bitte wiederhole deine Eingabe."
)

BUSY_NOTICE = (
    "Bin noch bei deiner letzten Nachricht. "
    "Schick gleich nochmal, wenn die Antwort da ist."
)

_lock = threading.RLock()
_seen_updates: OrderedDict[str, float] = OrderedDict()
_seen_messages: OrderedDict[str, float] = OrderedDict()
_busy_notice_at: dict[str, float] = {}
_history: dict[str, list[dict[str, str]]] = {}

# Begrenzt parallele Webhook-Worker (kein Thread-Flood)
POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="tg-nils")


def _prune(cache: OrderedDict[str, float], now: float, ttl: float) -> None:
    while cache:
        key, ts = next(iter(cache.items()))
        if now - ts <= ttl:
            break
        cache.popitem(last=False)


def remember_incoming(
    *,
    update_id: int | None,
    chat_id: str = "",
    message_id: int | None = None,
) -> bool:
    """True = neu / verarbeiten. False = Duplikat innerhalb DEDUP_TTL_SEC."""
    now = time.time()
    with _lock:
        _prune(_seen_updates, now, DEDUP_TTL_SEC)
        _prune(_seen_messages, now, DEDUP_TTL_SEC)

        if update_id is not None:
            ukey = f"u:{int(update_id)}"
            if ukey in _seen_updates and (now - _seen_updates[ukey]) < DEDUP_TTL_SEC:
                return False
            _seen_updates[ukey] = now
            # OrderedDict move to end
            _seen_updates.move_to_end(ukey)

        mid = int(message_id or 0)
        cid = str(chat_id or "").strip()
        if mid and cid:
            mkey = f"m:{cid}:{mid}"
            if mkey in _seen_messages and (now - _seen_messages[mkey]) < DEDUP_TTL_SEC:
                return False
            _seen_messages[mkey] = now
            _seen_messages.move_to_end(mkey)

        # Ohne update_id und ohne message_id: nicht blind erlauben doppelt
        if update_id is None and not (mid and cid):
            return False
        return True


def should_send_busy_notice(chat_id: str) -> bool:
    now = time.time()
    cid = str(chat_id or "")
    with _lock:
        last = _busy_notice_at.get(cid, 0.0)
        if now - last < BUSY_NOTICE_TTL:
            return False
        _busy_notice_at[cid] = now
        return True


def append_turn(chat_id: str, role: str, body: str) -> None:
    """Nur user|assistant. System-Prompts gehören nie in die History."""
    r = (role or "").strip().lower()
    if r in ("bot", "nils", "assistant"):
        r = "assistant"
    elif r in ("user", "christian", "human"):
        r = "user"
    else:
        return
    text = (body or "").strip()
    if not text:
        return
    cid = str(chat_id or "").strip()
    if not cid:
        return
    with _lock:
        turns = _history.setdefault(cid, [])
        turns.append({"role": r, "body": text[:4000]})
        if len(turns) > HISTORY_MAX_TURNS:
            del turns[: len(turns) - HISTORY_MAX_TURNS]


def get_turns(chat_id: str, limit: int = 6) -> list[dict[str, str]]:
    """[{role, body}] nur user/assistant, chronologisch."""
    cid = str(chat_id or "").strip()
    with _lock:
        turns = list(_history.get(cid) or [])
    return turns[-max(1, int(limit)) :]


def clear_chat(chat_id: str) -> None:
    with _lock:
        _history.pop(str(chat_id or ""), None)


def normalize_history_for_llm(history: list[dict[str, Any]], *, limit: int = 6) -> list[dict[str, str]]:
    """Fremde Rollen (system, tool, …) rausfiltern. Nie System→User mappen."""
    out: list[dict[str, str]] = []
    for h in history or []:
        raw = (h.get("role") or "").strip().lower()
        if raw in ("assistant", "bot", "nils"):
            role = "assistant"
        elif raw in ("user", "christian", "human"):
            role = "user"
        else:
            continue
        body = (h.get("body") or h.get("content") or "").strip()
        if not body:
            continue
        out.append({"role": role, "body": body})
    return out[-max(1, int(limit)) :]


def build_llm_messages(
    *,
    system: str,
    user_text: str,
    history: list[dict[str, Any]] | None = None,
    history_limit: int = 6,
    user_prefix: str = "",
) -> list[dict[str, str]]:
    """Glasklare Struktur: 1× system, dann nur user/assistant Turns, dann aktuelle user-Msg."""
    messages: list[dict[str, str]] = [{"role": "system", "content": (system or "").strip()}]
    for turn in normalize_history_for_llm(history or [], limit=history_limit):
        messages.append({"role": turn["role"], "content": turn["body"]})
    content = (user_text or "").strip()
    if user_prefix:
        content = f"{user_prefix.rstrip()}\n\n{content}".strip()
    messages.append({"role": "user", "content": content or "…"})
    return messages
