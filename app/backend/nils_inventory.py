# -*- coding: utf-8 -*-
"""Nils Fähigkeits-Inventar – weiß, was er hat, greift selbst danach.

Wird in jeden Companion-/Orchestrator-Prompt gelegt.
Live-Check: Keys da? Module da? Was fehlt?
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve()
ROOT = _HERE.parents[2]
for cand in (_HERE.parents[1], _HERE.parents[2]):
    if (cand / "akquise").is_dir() or (cand / "deploy.secrets.local").is_file():
        ROOT = cand
        break

_CACHE: dict[str, Any] = {"ts": 0.0, "text": "", "data": {}}


def _env(name: str) -> str:
    v = (os.environ.get(name) or "").strip()
    if v:
        return v
    for base in (ROOT, ROOT / "app", Path("/root/app"), _HERE.parents[1]):
        for fname in (
            "deploy.secrets.local",
            "requesty.secrets.local",
            "cursor.secrets.local",
            ".env",
            "backend/.env",
        ):
            p = base / fname if fname != "backend/.env" else base / "backend" / ".env"
            if not p.is_file():
                # also /root/app/backend/.env style
                continue
            try:
                for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                    s = line.strip()
                    if not s or s.startswith("#") or "=" not in s:
                        continue
                    k, _, val = s.partition("=")
                    if k.strip() == name:
                        return val.strip().strip('"').strip("'")
            except Exception:
                continue
    # /root/app/backend/.env
    for p in (
        Path("/root/app/backend/.env"),
        Path("/root/app/deploy.secrets.local"),
        Path("/root/app/requesty.secrets.local"),
        Path("/root/app/cursor.secrets.local"),
    ):
        if not p.is_file():
            continue
        try:
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                s = line.strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                k, _, val = s.partition("=")
                if k.strip() == name:
                    return val.strip().strip('"').strip("'")
        except Exception:
            continue
    return ""


def _has(name: str) -> bool:
    return bool(_env(name))


def snapshot(*, force: bool = False) -> dict[str, Any]:
    """Live-Inventar. Cache 60s."""
    now = time.time()
    if not force and _CACHE["data"] and now - float(_CACHE["ts"]) < 60:
        return dict(_CACHE["data"])

    caps: list[dict[str, Any]] = []

    def add(cid: str, label: str, ready: bool, how: str, *, freigabe: bool = False):
        caps.append(
            {
                "id": cid,
                "label": label,
                "ready": ready,
                "how": how,
                "freigabe": freigabe,
            }
        )

    add("chat", "Normales Gespräch / Ideen", True, "Companion-LLM")
    add("memory", "Langzeitgedächtnis (Jahre)", True, "merk dir: / gedächtnis")
    add("deep_research", "Deep Research", True, "Web+Register+Places+Crawl")
    add("web", "Live-Suche / Wetter / Wiki", True, "web_context")
    add(
        "openregister",
        "OpenRegister / Handelsregister",
        _has("OPENREGISTER_API_KEY"),
        "deep_research / register_lookup",
    )
    add(
        "places",
        "Google Places",
        _has("GOOGLE_PLACES_API_KEY"),
        "deep_research",
    )
    fire = _has("FIRECRAWL_API_KEY") or _has("FIRECRAWL_KEY")
    add(
        "firecrawl",
        "Firecrawl Website-Scrape",
        fire,
        "deep_research (sonst lokaler Crawl)",
    )
    add("scrape_local", "Lokaler Website-Crawl", True, "scrape_website / Fallback")
    add(
        "cursor",
        "Cursor Cloud Agent (Programmieren)",
        _has("CURSOR_API_KEY"),
        "cursor_code",
        freigabe=True,
    )
    add(
        "requesty",
        "Requesty LLM / Vision / Bild",
        _has("PRIMARY_API_KEY") or _has("REQUESTY_API_KEY"),
        "Chat + optional Bild nach Quote",
        freigabe=True,
    )
    add("guardian", "Ops-Guardian / Dual", True, "guardian / dual_status")
    add("kunden", "Kundenstatus / CRM", True, "list_kunden / kunde_status")
    add("sales", "Sales / Meeting-Scan / Angebot", True, "meeting_scan / send_offer", freigabe=True)
    add("mail", "Kunden-Mail senden", True, "send_mail", freigabe=True)
    add("docs", "Angebot/Rechnung/Onboarding-Entwurf", True, "draft_document")
    add("golf", "Golfclub-Text (DGV)", True, "golf_club_text")
    add("instagram_caption", "Instagram-Caption", True, "instagram_caption")
    add("instagram_publish", "Instagram Meta-Upload", False, "Stub – Token/Pipeline fehlt", freigabe=True)
    add("n8n", "n8n Workflows anstoßen", True, "Orchestrator-Webhook (fail-open)")
    add("orchestrator", "Chef-Hirn Team+LLM-Route", True, "bei Bau/Deploy/Cursor")
    add("ux_gate", "Fact+UX-Gate vor fertig", True, "ux check URL/Datei")
    add("guided", "Cursor-Level Führung", True, "Fragen+Vorschläge vor Aktion")

    ready = [c for c in caps if c["ready"]]
    missing = [c for c in caps if not c["ready"]]
    data = {
        "as_of": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "capabilities": caps,
        "ready_ids": [c["id"] for c in ready],
        "missing_ids": [c["id"] for c in missing],
        "ready_count": len(ready),
        "missing_count": len(missing),
    }
    _CACHE["ts"] = now
    _CACHE["data"] = data
    _CACHE["text"] = ""
    return data


def for_prompt(*, compact: bool = True) -> str:
    """Textblock: Nils weiß, was er hat."""
    data = snapshot()
    if compact and _CACHE.get("text") and time.time() - float(_CACHE["ts"]) < 60:
        # rebuild if empty
        pass
    ready = [c for c in data["capabilities"] if c["ready"]]
    missing = [c for c in data["capabilities"] if not c["ready"]]
    lines = [
        "=== DEIN WERKZEUGKASTEN (live, du darfst selbst zugreifen) ===",
        "Du entscheidest selbst, wann du welches Werkzeug brauchst. Christian muss die Tools nicht nennen.",
        "Fakten brauchen → Research/Places/Register/Crawl. Code → Cursor (Freigabe). Mail → Freigabe.",
        "Unbekanntes nicht erfinden. Fehlt ein Key: ehrlich sagen.",
        "Bereit:",
    ]
    for c in ready:
        freig = " [Freigabe]" if c.get("freigabe") else ""
        lines.append(f"• {c['label']}{freig} → {c['how']}")
    if missing:
        lines.append("Noch nicht / Stub:")
        for c in missing:
            lines.append(f"• {c['label']} → {c['how']}")
    lines.append("=== ENDE WERKZEUGKASTEN ===")
    text = "\n".join(lines)
    _CACHE["text"] = text
    return text


def status_for_christian() -> str:
    """Menschliche Kurzfassung für Telegram „was kannst du“ / inventory."""
    data = snapshot(force=True)
    ready = [c["label"] for c in data["capabilities"] if c["ready"]]
    missing = [c["label"] for c in data["capabilities"] if not c["ready"]]
    lines = [
        "Das habe ich gerade griffbereit:",
        ", ".join(ready[:16]) + ("…" if len(ready) > 16 else ""),
        "",
        f"Keys/Module live geprüft: {data['ready_count']} bereit, {data['missing_count']} offen/Stub.",
    ]
    if missing:
        lines.append("Fehlt oder Stub: " + ", ".join(missing))
    lines.append(
        "Du musst die Tools nicht nennen. Sag einfach den Auftrag, ich greife selbst danach."
    )
    return "\n".join(lines)


def suggest_reach(message: str) -> list[str]:
    """Welche Fähigkeiten passen zum Auftrag (für Fast-Match / Plan)."""
    t = (message or "").lower()
    out: list[str] = []
    data = snapshot()
    ready = set(data.get("ready_ids") or [])

    def want(cid: str, *keys: str) -> None:
        if cid in ready and any(k in t for k in keys):
            out.append(cid)

    want(
        "deep_research",
        "recherch",
        "analysier",
        "firma",
        "konkurrenz",
        "schau dir",
        "background",
        "finde info",
        "finde raus",
        "was weißt",
        "was weisst",
        "über die firma",
        "über den laden",
        "check die",
        "untersuch",
        "gmbh",
        "unternehmen",
    )
    want("web", "wetter", "news", "aktuell", "heute", "preis von", "kurs", "wer ist")
    want("openregister", "handelsregister", "geschäftsführer", "geschaeftsfuehrer", "gmbh", "holding")
    want("places", "places", "google maps", "bewertung", "restaurant", "imbiss", "öffnungszeit", "oeffnungszeit")
    want(
        "cursor",
        "programmier",
        "website",
        "im repo",
        "cursor:",
        "app bau",
        "bau die",
        "baue ",
        "fix den code",
        "deploy",
    )
    want("sales", "angebot", "meeting", "scan", "onboarding")
    want("mail", "mail an", "schick mail", "sende mail")
    want("guardian", "guardian", "server status", "dual", "down", "ops")
    want("golf", "dgv", "golfclub", "golf club")
    want("docs", "rechnung", "entwurf angebot", "onboarding text")
    want("instagram_caption", "instagram", "caption", "insta text")
    # dedupe preserve order
    seen: set[str] = set()
    uniq = []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq
