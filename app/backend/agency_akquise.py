# -*- coding: utf-8 -*-
"""Akquise-Freigaben API (approve / call_later / skip) + Reminder an Inhaber."""
from __future__ import annotations

import json
import os
import smtplib
import time
import uuid
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

# Lokal: .../Server/app/backend -> Repo-Root Server
# Server: /root/app/backend -> App-Root /root/app (docs liegen hier)
_APP = Path(__file__).resolve().parents[1]
_CANDIDATE_ROOTS = (_APP.parent, _APP)
ROOT = next(
    (p for p in _CANDIDATE_ROOTS if (p / "docs" / "akquise").is_dir() or (p / "akquise").is_dir()),
    _APP,
)
STORE = Path(os.environ.get("AKQUISE_APPROVALS", str(ROOT / "docs" / "akquise" / "approvals.json")))


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


def list_items(status: str | None = None) -> list[dict]:
    items = _load().get("items") or []
    if status:
        items = [i for i in items if i.get("status") == status]
    items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    return items


def upsert(
    *,
    key: str,
    status: str,
    name: str = "",
    phone: str = "",
    address: str = "",
    note: str = "",
    vertical: str = "",
    buy_summary: str = "",
    addon_pitch: str = "",
    call_script: str = "",
    roi_label: str = "",
) -> dict[str, Any]:
    if status not in ("approve", "call_later", "skip", "done"):
        raise ValueError("status muss approve|call_later|skip|done sein")
    if not key:
        raise ValueError("key fehlt")
    data = _load()
    items = data.get("items") or []
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    found = next((i for i in items if i.get("key") == key), None)
    if not found:
        found = {"id": str(uuid.uuid4())[:8], "key": key, "created_at": now}
        items.append(found)
    found.update(
        {
            "status": status,
            "updated_at": now,
            "note": note or found.get("note", ""),
            "vertical": vertical or found.get("vertical", ""),
            "name": name or found.get("name", ""),
            "phone": phone or found.get("phone", ""),
            "address": address or found.get("address", ""),
            "buy_summary": buy_summary or found.get("buy_summary", ""),
            "addon_pitch": addon_pitch or found.get("addon_pitch", ""),
            "call_script": call_script or found.get("call_script", ""),
            "roi_label": roi_label or found.get("roi_label", ""),
        }
    )
    if status == "call_later":
        found["remind_at"] = time.strftime("%Y-%m-%d", time.localtime(time.time() + 3 * 86400))
    data["items"] = items
    _save(data)
    return found


def latest_buy_queue(limit: int = 80) -> list[dict]:
    """Kaufbereite Leads aus den neuesten Vertical-Reports."""
    reports = ROOT / "docs" / "akquise" / "reports"
    if not reports.is_dir():
        return []
    files = sorted(reports.glob("*-*-*.json"), reverse=True)
    # skip demand/news/market/approvals
    skip = ("demand", "local-news", "market", "approvals")
    out: list[dict] = []
    seen: set[str] = set()
    for path in files:
        stem = path.stem  # date-vertical
        if any(s in stem for s in skip):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        vertical = data.get("vertical") or ""
        for lead in data.get("leads") or []:
            intent = lead.get("intent") or {}
            if not intent.get("buy_ready") and intent.get("contact_priority") != "call":
                continue
            if intent.get("budget_tier") not in ("A", "B"):
                continue
            key = ""
            gp = lead.get("google_places") or {}
            if gp.get("place_id"):
                key = f"place:{gp['place_id']}"
            else:
                key = f"{(lead.get('name') or '').lower()}|{round(float(lead.get('lat') or 0), 4)}|{round(float(lead.get('lon') or 0), 4)}"
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "key": key,
                    "name": lead.get("name") or "",
                    "phone": lead.get("phone") or intent.get("contact_phone") or "",
                    "address": lead.get("address") or "",
                    "vertical": vertical,
                    "budget_tier": intent.get("budget_tier"),
                    "buy_summary": intent.get("buy_summary") or "",
                    "addon_pitch": intent.get("addon_pitch") or "",
                    "call_script": intent.get("call_script_text") or "",
                    "roi_label": intent.get("roi_label") or "",
                    "report": path.name,
                }
            )
            if len(out) >= limit:
                return out
    return out


def due_reminders(today: str | None = None) -> list[dict]:
    today = today or time.strftime("%Y-%m-%d")
    return [
        i
        for i in list_items("call_later")
        if (i.get("remind_at") or "") <= today
    ]


def send_reminder_mail(items: list[dict], secrets: dict) -> dict:
    if not items:
        return {"ok": True, "sent": 0, "message": "keine Reminder fällig"}
    to = secrets.get("AGENCY_OWNER_EMAIL") or secrets.get("SMTP_USER") or ""
    host = secrets.get("SMTP_HOST") or ""
    user = secrets.get("SMTP_USER") or ""
    password = secrets.get("SMTP_PASSWORD") or ""
    port = int(secrets.get("SMTP_PORT") or 587)
    if not (to and host and user and password):
        return {"ok": False, "error": "SMTP/AGENCY_OWNER_EMAIL fehlt"}

    lines = ["Akquise-Reminder: Bitte nachfassen\n"]
    for it in items[:20]:
        lines.append(
            f"- {it.get('name','?')} | {it.get('phone','')} | "
            f"{it.get('buy_summary','')} | Reminder seit {it.get('remind_at')}"
        )
        if it.get("call_script"):
            lines.append(f"  Skript: {it['call_script'][:220]}")
    body = "\n".join(lines)
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = f"[Akquise] {len(items)} Rückruf(e) fällig"
    msg["From"] = user
    msg["To"] = to
    with smtplib.SMTP(host, port, timeout=30) as s:
        s.starttls()
        s.login(user, password)
        s.sendmail(user, [to], msg.as_string())
    return {"ok": True, "sent": len(items), "to": to}
