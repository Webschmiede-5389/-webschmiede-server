"""Branchen-Wissen laden (Bot, Voice, Inbox)."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

APP_ROOT = Path(__file__).resolve().parents[1]
PACKS_DIR = Path(os.getenv("KNOWLEDGE_DIR", APP_ROOT / "knowledge")) / "packs"

BRANCHE_PACK = {
    "restaurant": "gastro",
    "gastro": "gastro",
    "handwerk": "handwerk",
    "dach": "handwerk",
    "dental": "handwerk",
    "friseur": "handwerk",
    "beauty": "general",
}


def pack_for_branche(branche: str) -> str:
    b = (branche or "").strip().lower()
    return BRANCHE_PACK.get(b, "general")


def load_pack(pack_id: str) -> dict | None:
    pid = (pack_id or "").strip().lower()
    if not pid:
        return None
    path = PACKS_DIR / f"{pid}.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _merge_faqs(base: list[dict], overrides: list[dict]) -> list[dict]:
    by_id = {f.get("id"): dict(f) for f in base if f.get("id")}
    for ov in overrides or []:
        fid = ov.get("id")
        if not fid:
            continue
        if fid in by_id:
            by_id[fid].update({k: v for k, v in ov.items() if v is not None})
        else:
            by_id[fid] = dict(ov)
    return list(by_id.values())


def resolve_knowledge(kunde: dict) -> dict:
    """Pack + Kunden-Overrides zusammenführen."""
    kn = kunde.get("knowledge") or {}
    pack_id = kn.get("pack") or pack_for_branche(kunde.get("branche", ""))
    pack = load_pack(pack_id) or load_pack("general") or {"id": "general", "faqs": []}
    overrides = kn.get("overrides") or {}
    faqs = _merge_faqs(pack.get("faqs") or [], overrides.get("faqs") or [])
    voice = {**(pack.get("voice") or {}), **(kn.get("voice") or {})}
    for key in ("greeting", "fallback"):
        if key in voice and isinstance(voice[key], str):
            voice[key] = voice[key].replace("{business_name}", kunde.get("name", "uns"))
    return {
        "pack_id": pack.get("id", pack_id),
        "pack_label": pack.get("label", pack_id),
        "locale": kn.get("locale") or pack.get("locale", "de-DE"),
        "topics": pack.get("topics") or [],
        "faqs": faqs,
        "voice": voice,
        "kunde_id": kunde.get("id", ""),
    }


def resolve_for_kid(kunde: dict | None) -> dict | None:
    if not kunde:
        return None
    return resolve_knowledge(kunde)


def find_faq_answer(knowledge: dict, text: str) -> dict | None:
    """Keyword-Suche: exakter Substring oder alle Wörter eines Keywords im Text."""
    t = (text or "").lower()
    if not t:
        return None
    best = None
    best_score = 0
    for faq in knowledge.get("faqs") or []:
        score = 0
        for kw in faq.get("keywords") or []:
            kwl = kw.lower().strip()
            if not kwl:
                continue
            if kwl in t:
                score += 3
                continue
            parts = [p for p in kwl.split() if len(p) > 2]
            if len(parts) >= 2 and all(p in t for p in parts):
                score += 2
            elif len(parts) == 1 and parts[0] in t:
                score += 1
        if score > best_score:
            best_score = score
            best = faq
    return best if best_score > 0 else None
