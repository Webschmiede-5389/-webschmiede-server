"""Radar (Trend-Scout): Markt, OSS, APIs, Wissensquellen beobachten.

Kein Auto-Install. Christian gibt frei („install X“), dann Nils.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "docs" / "agency" / "reports"
QUEUE_PATH = ROOT / "agency" / "radar_queue.json"

# Kuratierte Quellen (Foren/Feeds/Docs) – ehrlich, kein Scraping-Wahn
SOURCES: list[dict[str, str]] = [
    {"id": "hf", "name": "Hugging Face Models API", "url": "https://huggingface.co/api/models?sort=downloads&limit=8", "cat": "llm"},
    {"id": "gh_n8n", "name": "GitHub n8n", "url": "https://api.github.com/repos/n8n-io/n8n/releases/latest", "cat": "automation"},
    {"id": "gh_ollama", "name": "GitHub Ollama", "url": "https://api.github.com/repos/ollama/ollama/releases/latest", "cat": "llm"},
    {"id": "awesome_selfhosted", "name": "awesome-selfhosted README", "url": "https://raw.githubusercontent.com/awesome-selfhosted/awesome-selfhosted/master/README.md", "cat": "oss"},
]

WATCH_FORUMS = [
    {"name": "n8n Community", "url": "https://community.n8n.io/", "note": "Nodes, Patterns, Breaking Changes"},
    {"name": "r/selfhosted", "url": "https://www.reddit.com/r/selfhosted/", "note": "OSS Alternativen, DE-Hosting-Fit"},
    {"name": "Hacker News", "url": "https://news.ycombinator.com/", "note": "APIs/Tools die viral gehen"},
    {"name": "Hugging Face Blog", "url": "https://huggingface.co/blog", "note": "Modelle, lokale Inference"},
    {"name": "Cloudflare Blog", "url": "https://blog.cloudflare.com/", "note": "Workers, Email, Security"},
]

STACK_GAPS = [
    "Instagram Content-Queue mit Freigabe",
    "WhatsApp Meta Token live (Inbound)",
    "Postgres wenn Multi-Kunde/Trigger",
    "Wissensdatenbank pro Kunde (Packs)",
    "Lokale LLM-Demos ohne API-Kosten",
]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _http_get(url: str, timeout: int = 20) -> tuple[bool, str]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "WebschmiedeRadar/1.0 (+digitalehandwerkskunst.de)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return True, r.read().decode("utf-8", errors="replace")
    except Exception as e:
        return False, str(e)[:200]


def fetch_signals(*, live: bool = True) -> list[dict[str, Any]]:
    """Holt kurze Signale aus öffentlichen APIs. Fail-open pro Quelle."""
    signals: list[dict[str, Any]] = []
    if not live:
        return signals
    # HF models
    ok, body = _http_get(SOURCES[0]["url"])
    if ok:
        try:
            models = json.loads(body)
            for m in (models or [])[:5]:
                mid = m.get("modelId") or m.get("id") or "?"
                signals.append(
                    {
                        "source": "huggingface",
                        "cat": "llm",
                        "title": mid,
                        "meta": f"downloads≈{m.get('downloads')}",
                        "url": f"https://huggingface.co/{mid}",
                        "fit": "spaeter" if "gguf" not in mid.lower() else "ja",
                    }
                )
        except Exception as e:
            signals.append({"source": "huggingface", "error": str(e)[:120]})
    else:
        signals.append({"source": "huggingface", "error": body})

    for src in SOURCES[1:3]:
        ok, body = _http_get(src["url"])
        if ok:
            try:
                rel = json.loads(body)
                signals.append(
                    {
                        "source": src["id"],
                        "cat": src["cat"],
                        "title": rel.get("tag_name") or rel.get("name") or src["name"],
                        "meta": (rel.get("published_at") or "")[:10],
                        "url": rel.get("html_url") or src["url"],
                        "fit": "ja",
                    }
                )
            except Exception as e:
                signals.append({"source": src["id"], "error": str(e)[:120]})
        else:
            signals.append({"source": src["id"], "error": body})

    # awesome-selfhosted: nur Kopf + Treffer auf Keywords
    ok, body = _http_get(SOURCES[3]["url"], timeout=25)
    if ok:
        hits = []
        low = body.lower()
        for kw in ("n8n", "docuseal", "ollama", "meilisearch", "umami", "plausible", "outline", "affine"):
            if kw in low:
                hits.append(kw)
        signals.append(
            {
                "source": "awesome-selfhosted",
                "cat": "oss",
                "title": "Keyword-Treffer in awesome-selfhosted",
                "meta": ", ".join(hits[:12]) or "keine Kern-Keywords",
                "url": "https://github.com/awesome-selfhosted/awesome-selfhosted",
                "fit": "ja" if hits else "spaeter",
            }
        )
    else:
        signals.append({"source": "awesome-selfhosted", "error": body})
    return signals


def improve_audit() -> dict[str, Any]:
    """Prüft, ob Workflows/Stack „wach“ bleiben (kein Blind-Install)."""
    checks: list[dict[str, Any]] = []
    reports = sorted(REPORTS.glob("*-radar.md")) if REPORTS.is_dir() else []
    last = reports[-1].name if reports else None
    checks.append(
        {
            "id": "radar_report",
            "ok": bool(reports),
            "detail": f"letzter Report: {last}" if last else "kein Radar-Report",
        }
    )
    queue = load_queue()
    pending = [x for x in queue.get("items") or [] if x.get("status") == "pending"]
    checks.append(
        {
            "id": "install_queue",
            "ok": True,
            "detail": f"{len(pending)} wartend auf Christians OK",
        }
    )
    brain = (ROOT / "app" / "backend" / "agency_brain.py").is_file()
    checks.append({"id": "agency_brain", "ok": brain, "detail": "agency_brain.py"})
    dual = (ROOT / "app" / "backend" / "dual_infra.py").is_file()
    checks.append({"id": "dual_infra", "ok": dual, "detail": "dual_infra.py"})
    hooks = (ROOT / ".cursor" / "hooks.json").is_file()
    checks.append({"id": "cursor_hooks", "ok": hooks, "detail": "Hirn-Hooks"})
    return {
        "ok": all(c.get("ok") for c in checks if c["id"] != "install_queue"),
        "as_of": _now(),
        "checks": checks,
        "stack_gaps": STACK_GAPS,
        "note": "Verbesserung = Report + Lücken schließen nach Freigabe, nicht Tool-Hopping.",
    }


def load_queue() -> dict[str, Any]:
    if not QUEUE_PATH.is_file():
        return {"ok": True, "items": [], "updated_at": None}
    try:
        return json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"ok": False, "items": [], "error": "queue corrupt"}


def save_queue(data: dict[str, Any]) -> None:
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = _now()
    QUEUE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def queue_install(
    name: str,
    *,
    reason: str = "",
    category: str = "tool",
    cost: str = "unbekannt",
    url: str = "",
) -> dict[str, Any]:
    name = (name or "").strip()
    if not name:
        return {"ok": False, "error": "name fehlt"}
    q = load_queue()
    items = list(q.get("items") or [])
    for it in items:
        if it.get("name", "").lower() == name.lower() and it.get("status") == "pending":
            return {"ok": True, "item": it, "note": "schon in Queue"}
    item = {
        "id": f"rad{len(items)+1:03d}",
        "name": name[:120],
        "category": category[:40],
        "cost": cost[:60],
        "reason": reason[:500],
        "url": url[:300],
        "status": "pending",
        "created_at": _now(),
        "auto_install": False,
    }
    items.append(item)
    q["items"] = items
    save_queue(q)
    return {"ok": True, "item": item, "note": "Wartet auf Christians OK. Kein Auto-Install."}


def approve_install(item_id: str, *, approve: bool = True) -> dict[str, Any]:
    """Nur Status setzen. Echtes Install macht Nils nach OK."""
    q = load_queue()
    items = list(q.get("items") or [])
    for it in items:
        if it.get("id") == item_id:
            it["status"] = "approved" if approve else "rejected"
            it["decided_at"] = _now()
            q["items"] = items
            save_queue(q)
            return {
                "ok": True,
                "item": it,
                "next": "Nils: Install + Smoke-Test nur wenn approved"
                if approve
                else "verworfen",
            }
    return {"ok": False, "error": "id nicht gefunden"}


def build_report(*, live: bool = True, day: str | None = None) -> dict[str, Any]:
    day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    signals = fetch_signals(live=live)
    audit = improve_audit()
    queue = load_queue()
    pending = [x for x in (queue.get("items") or []) if x.get("status") == "pending"]

    top: list[dict[str, Any]] = []
    for s in signals:
        if s.get("error"):
            continue
        top.append(
            {
                "name": s.get("title"),
                "cat": s.get("cat"),
                "cost": "meist 0 / self-host oder API",
                "fit": s.get("fit") or "spaeter",
                "note": s.get("meta") or "",
                "url": s.get("url") or "",
            }
        )
        if len(top) >= 5:
            break
    while len(top) < 5:
        top.append({"name": "_offen_", "cat": "", "cost": "", "fit": "", "note": "manuell ergänzen", "url": ""})

    sellable = [
        "Portal + Monats-Ops (Watchdog inklusive)",
        "Standort-Pilot Baustoff (WA/Preislisten/Reklamation)",
        "Voice-Demo Call + Portal-Upsell",
    ]

    lines = [
        f"# Radar {day}",
        "",
        f"> Automatisch · {_now()} · Mitarbeiter **Radar** (unter Stefan, Install durch Nils)",
        "> Regel: **nichts installieren ohne Freigabe von Christian.**",
        "",
        "## Auftrag",
        "",
        "- Markt/OSS/APIs sichten",
        "- Workflows & Stack auf Lücken prüfen",
        "- Install-Kandidaten in Queue legen",
        "- Foren/Quellen manuell im Blick behalten (Links unten)",
        "",
        "## Top-Signale (live wo möglich)",
        "",
        "| # | Name | Kategorie | Fit | Notiz |",
        "|---|------|-----------|-----|-------|",
    ]
    for i, t in enumerate(top, 1):
        lines.append(
            f"| {i} | {t['name']} | {t['cat']} | {t['fit']} | {(t['note'] or '')[:80]} |"
        )
    lines += [
        "",
        "## Neu verkaufbar",
        "",
    ]
    for s in sellable:
        lines.append(f"- [ ] {s}")
    lines += [
        "",
        "## Install-Queue (warten auf OK)",
        "",
    ]
    if pending:
        for p in pending:
            lines.append(f"- `{p['id']}` **{p['name']}** – {p.get('reason') or p.get('cost')} ({p.get('category')})")
    else:
        lines.append("- (leer)")
    lines += [
        "",
        "## Stack-Audit (werden wir besser?)",
        "",
    ]
    for c in audit.get("checks") or []:
        mark = "OK" if c.get("ok") else "LÜCKE"
        lines.append(f"- [{mark}] {c['id']}: {c.get('detail')}")
    lines += [
        "",
        "## Offene Stack-Lücken",
        "",
    ]
    for g in STACK_GAPS:
        lines.append(f"- {g}")
    lines += [
        "",
        "## Foren / Wissensquellen (manuell prüfen)",
        "",
    ]
    for f in WATCH_FORUMS:
        lines.append(f"- [{f['name']}]({f['url']}) – {f['note']}")
    lines += [
        "",
        "## Verworfen / bewusst nicht",
        "",
        "- GoHighLevel",
        "- Blind Auto-Install / Auto-Posting",
        "- US-SaaS ohne DSGVO-Check für Kundendaten",
        "",
        "## Nächste Frage an Christian",
        "",
        "Ein Thema diese Woche vertiefen – und ggf. einen Queue-Eintrag freigeben (`approve <id>`).",
        "",
    ]
    markdown = "\n".join(lines)
    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / f"{day}-radar.md"
    path.write_text(markdown, encoding="utf-8")
    return {
        "ok": True,
        "agent": "radar",
        "workflow": "radar",
        "day": day,
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "signals": signals,
        "top": top,
        "audit": audit,
        "pending_installs": pending,
        "forums": WATCH_FORUMS,
        "auto_install": False,
        "markdown": markdown,
        "as_of": _now(),
    }


def status() -> dict[str, Any]:
    reports = sorted(REPORTS.glob("*-radar.md")) if REPORTS.is_dir() else []
    return {
        "ok": True,
        "agent": "radar",
        "label": "Radar / Trend-Scout",
        "reports_count": len(reports),
        "last_report": reports[-1].name if reports else None,
        "queue": load_queue(),
        "audit": improve_audit(),
        "auto_install": False,
        "role": (
            "Beobachtet Markt, OSS, APIs, Foren-Links. "
            "Schreibt Wochenreport. Legt Install-Kandidaten in Queue. "
            "Install nur nach Christians OK durch Nils."
        ),
    }
