# -*- coding: utf-8 -*-
"""Akquise-Freigaben: anrufen / später / skip (UWG: kein Auto-Kontakt)."""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "docs" / "akquise" / "approvals.json"


def _load() -> dict:
    if STORE.exists():
        try:
            return json.loads(STORE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"items": []}
    return {"items": []}


def _save(data: dict) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def lead_key(lead: dict) -> str:
    pid = (lead.get("google_places") or {}).get("place_id") or ""
    if pid:
        return f"place:{pid}"
    name = (lead.get("name") or "").strip().lower()
    lat = round(float(lead.get("lat") or 0), 4)
    lon = round(float(lead.get("lon") or 0), 4)
    return f"{name}|{lat}|{lon}"


def upsert_decision(
    *,
    key: str,
    status: str,
    lead: dict | None = None,
    note: str = "",
    vertical: str = "",
) -> dict[str, Any]:
    """status: approve | call_later | skip | done"""
    if status not in ("approve", "call_later", "skip", "done"):
        raise ValueError("status ungültig")
    data = _load()
    items = data.get("items") or []
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    found = None
    for it in items:
        if it.get("key") == key:
            found = it
            break
    if not found:
        found = {"id": str(uuid.uuid4())[:8], "key": key, "created_at": now}
        items.append(found)
    found["status"] = status
    found["updated_at"] = now
    found["note"] = note or found.get("note", "")
    found["vertical"] = vertical or found.get("vertical", "")
    if lead:
        found["name"] = lead.get("name") or found.get("name", "")
        found["phone"] = lead.get("phone") or (lead.get("intent") or {}).get("contact_phone") or found.get("phone", "")
        found["address"] = lead.get("address") or found.get("address", "")
        intent = lead.get("intent") or {}
        found["buy_summary"] = intent.get("buy_summary") or found.get("buy_summary", "")
        found["addon_pitch"] = intent.get("addon_pitch") or found.get("addon_pitch", "")
        found["call_script"] = intent.get("call_script_text") or found.get("call_script", "")
        found["roi_label"] = intent.get("roi_label") or found.get("roi_label", "")
    if status == "call_later" and not found.get("remind_at"):
        # +3 Tage
        found["remind_at"] = time.strftime(
            "%Y-%m-%d", time.localtime(time.time() + 3 * 86400)
        )
    data["items"] = items
    _save(data)
    return found


def list_decisions(status: str | None = None) -> list[dict]:
    items = _load().get("items") or []
    if status:
        items = [i for i in items if i.get("status") == status]
    items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    return items


def due_reminders(today: str | None = None) -> list[dict]:
    today = today or time.strftime("%Y-%m-%d")
    out = []
    for it in list_decisions("call_later"):
        if (it.get("remind_at") or "") <= today:
            out.append(it)
    return out
