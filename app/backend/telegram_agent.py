"""Telegram Agency-Agent: Christian ↔ Nils/Stefan + Tools (Kunden, Sales, Ops).

Kein Cursor-Ersatz (kein Repo-Edit). Wohl: Hirn-Routing, Aktionen mit Freigabe,
Ollama (starkes lokales Modell) für normales Gespräch.
"""
from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

import agency_brain as brain
import agency_cockpit as cockpit
import llm_client as llm
import ops_guardian as guardian
import sales_pipeline as sales

KID_RE = re.compile(r"\b(SHY\d{3})\b", re.I)
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)
DOMAIN_RE = re.compile(
    r"\b(?:www\.)?[a-z0-9][a-z0-9\-.]{1,60}\.(?:de|com|net|at|ch|eu|io|org)\b",
    re.I,
)
YES = frozenset({"ja", "yes", "ok", "okay", "mach", "los", "bestätigen", "bestaetigen", "senden"})
NO = frozenset({"nein", "abbrechen", "cancel", "stop"})

try:
    import nils_tools as _nils_tools
except Exception:  # pragma: no cover
    _nils_tools = None  # type: ignore

RISKY = frozenset({
    "send_offer",
    "send_onboarding",
    "sales_invite",
    "sales_freigabe",
    "sales_set_price",
    "send_mail",
    "instagram_publish",
    "cursor_code",
})
if _nils_tools is not None:
    RISKY = frozenset(RISKY | getattr(_nils_tools, "RISKY_TOOLS", frozenset()))


def extract_meeting_entities(text: str) -> dict[str, str]:
    """Website + Mail (+ grobe Firma) aus freiem Text ziehen."""
    raw = text or ""
    emails = EMAIL_RE.findall(raw)
    urls = URL_RE.findall(raw)
    website = ""
    if urls:
        website = urls[0].rstrip(").,;")
    else:
        for d in DOMAIN_RE.findall(raw):
            if "@" in d:
                continue
            d = d.strip().rstrip(").,;")
            website = "https://" + d
            break
    email = emails[0].lower() if emails else ""
    firma = ""
    # „Firma X“ / „bei X“
    m = re.search(r"(?:firma|betrieb|kunde|bei)\s+([A-ZÄÖÜ][\wÄÖÜäöüß &\-]{2,40})", raw)
    if m:
        firma = m.group(1).strip()
    return {"website": website, "email": email, "firma": firma}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower().strip())


def parse_force_agent(text: str) -> tuple[str | None, str]:
    t = (text or "").strip()
    low = t.lower()
    for prefix, agent in (
        ("stefan:", "stefan"),
        ("@stefan", "stefan"),
        ("hey stefan", "stefan"),
        ("stefan,", "stefan"),
        ("nils:", "nils"),
        ("@nils", "nils"),
        ("hey nils", "nils"),
        ("nils,", "nils"),
        ("radar:", "radar"),
        ("scout:", "scout"),
        ("anwalt:", "anwalt"),
    ):
        if low.startswith(prefix):
            rest = t[len(prefix) :].lstrip(" :,")
            return agent, rest or t
    # „frag stefan …“ / „sag nils …“
    m = re.match(r"^(frag|sag|an)\s+(stefan|nils|radar|scout|anwalt)\b[:\s,]*(.*)$", low)
    if m:
        agent = m.group(2)
        # Original-Rest behalten (Groß/Klein)
        rest = re.sub(
            r"^(frag|sag|an)\s+(stefan|nils|radar|scout|anwalt)\b[:\s,]*",
            "",
            t,
            count=1,
            flags=re.I,
        ).strip()
        return agent, rest or t
    return None, t


def _tool_list_kunden() -> dict[str, Any]:
    rows = cockpit.list_kunden_summary() or []
    lines = []
    for r in rows[:20]:
        lines.append(
            f"{r.get('id')}: {r.get('name')} · {r.get('status')} · "
            f"{r.get('progress_percent', '?')}%"
        )
    return {"ok": True, "count": len(rows), "text": "\n".join(lines) or "Keine Kunden."}


def _tool_kunde_status(kid: str) -> dict[str, Any]:
    d = cockpit.get_kunde_detail(kid.upper())
    if not d:
        return {"ok": False, "error": f"Kunde {kid} nicht gefunden"}
    open_pts = d.get("open_points") or []
    text = (
        f"{d.get('name')} ({kid.upper()})\n"
        f"Status: {d.get('status')} · Fortschritt {(d.get('progress') or {}).get('percent')}%\n"
        f"Inhaber: {d.get('inhaber') or '–'}\n"
        f"Mail: {(d.get('kontakt') or {}).get('email') or '–'}\n"
        f"Subdomain: {(d.get('urls') or {}).get('subdomain') or '–'}\n"
        f"Offen: {'; '.join(open_pts[:5]) if open_pts else '–'}"
    )
    return {"ok": True, "kunde_id": kid.upper(), "text": text, "detail": d}


def _tool_sales_deals(db: sqlite3.Connection) -> dict[str, Any]:
    data = sales.list_deals(db, limit=15)
    deals = data.get("deals") or []
    lines = []
    for d in deals[:12]:
        if not isinstance(d, dict):
            continue
        lines.append(
            f"{d.get('id')}: {d.get('firma') or d.get('email')} · {d.get('status')} · "
            f"{d.get('product') or ''}"
        )
    return {"ok": True, "text": "\n".join(lines) or "Keine Deals.", "count": len(lines)}


def _tool_dual() -> dict[str, Any]:
    res = brain.process("Dual Status Server", force_agent="nils", source="telegram", fast=False)
    nils = (res.get("results") or {}).get("nils") or {}
    dual = nils.get("dual") or {}
    text = (
        f"Web: {'ok' if (dual.get('web') or {}).get('ok') else 'ALARM'} · "
        f"API {(dual.get('web') or {}).get('snack_api')}\n"
        f"Auto: {'ok' if (dual.get('auto') or {}).get('ok') else 'ALARM'} · "
        f"n8n {(dual.get('auto') or {}).get('n8n')}\n"
        f"Alerts: {', '.join(dual.get('alerts') or []) or 'keine'}"
    )
    return {"ok": bool(nils.get("ok")), "text": text, "raw": nils}


def _tool_guardian() -> dict[str, Any]:
    try:
        r = guardian.status()
        if not r or r.get("stale"):
            r = guardian.run(repair=True, mail=False)
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}
    if not isinstance(r, dict):
        return {"ok": True, "text": str(r)[:1500]}
    text = r.get("summary") or r.get("markdown") or json.dumps(
        {k: r.get(k) for k in ("ok", "level", "alerts", "as_of") if k in r},
        ensure_ascii=False,
    )[:1200]
    return {"ok": r.get("ok", True), "text": str(text)[:2000]}


def _tool_shipcheck(url: str) -> dict[str, Any]:
    import agency_shipcheck as ship

    r = ship.gate_before_share(url) if hasattr(ship, "gate_before_share") else ship.check_url(url)
    return {
        "ok": bool(r.get("ship") or r.get("ok")),
        "text": r.get("summary") or json.dumps(r, ensure_ascii=False)[:800],
        "ship": r.get("ship"),
    }


def _tool_brain(message: str, force_agent: str | None) -> dict[str, Any]:
    res = brain.process(
        message,
        source="telegram",
        force_agent=force_agent,
        dispatch=True,
        include_commander=("commander" in (message or "").lower() or "tagesplan" in (message or "").lower()),
        fast=False,
        max_agents=4,
    )
    # Menschliche Kurzfassung aus summary + Playbook
    parts = [res.get("summary") or ""]
    if res.get("playbook"):
        parts.append("Playbook:\n" + str(res.get("playbook"))[:1200])
    # Stefan-Details
    stefan = (res.get("results") or {}).get("stefan")
    if isinstance(stefan, dict) and stefan.get("ok"):
        for key in ("empfehlung", "urteil", "plan", "next", "todos", "summary"):
            if stefan.get(key):
                parts.append(f"Stefan/{key}: {json.dumps(stefan.get(key), ensure_ascii=False)[:900]}")
                break
        # dump useful fields
        blob = {k: stefan[k] for k in list(stefan)[:12] if k not in ("ok",)}
        parts.append(json.dumps(blob, ensure_ascii=False)[:1500])
    return {
        "ok": bool(res.get("ok") or res.get("sharp")),
        "text": "\n\n".join(p for p in parts if p)[:3500],
        "agents": res.get("agents"),
        "route": (res.get("route") or {}).get("ziel"),
    }


def execute_tool(
    db: sqlite3.Connection,
    name: str,
    args: dict[str, Any] | None = None,
    *,
    confirmed: bool = False,
) -> dict[str, Any]:
    args = args or {}
    if name in RISKY and not confirmed:
        hint = f"Risiko-Aktion **{name}**. Antworte mit „ja“ zum Ausführen oder „abbrechen“."
        if name == "cursor_code":
            hint = (
                "Das startet einen Cursor-Cloud-Agenten am GitHub-Repo (kostet über Cursor). "
                "Wenn fertig: Auto-Deploy auf den Live-Server (braucht GITHUB_TOKEN). "
                "„ja“ zum Starten oder „abbrechen“."
            )
        return {
            "ok": False,
            "needs_confirm": True,
            "pending": {"tool": name, "args": args},
            "text": hint,
        }

    if name == "list_kunden":
        return _tool_list_kunden()
    if name == "kunde_status":
        kid = (args.get("kunde_id") or args.get("kid") or "").upper()
        if not kid:
            return {"ok": False, "error": "kunde_id fehlt"}
        return _tool_kunde_status(kid)
    if name == "sales_deals":
        return _tool_sales_deals(db)
    if name == "dual_status":
        return _tool_dual()
    if name == "guardian":
        return _tool_guardian()
    if name == "shipcheck":
        return _tool_shipcheck(args.get("url") or "")
    if name == "brain":
        return _tool_brain(args.get("message") or "", args.get("force_agent"))
    if name == "send_offer":
        kid = (args.get("kunde_id") or "").upper()
        pkg = args.get("package") or "starter"
        r = cockpit.send_offer(kid, package_id=pkg, note=args.get("note") or "")
        return {"ok": True, "text": f"Angebot {pkg} an {kid} ausgelöst: {r}", "raw": r}
    if name == "send_onboarding":
        kid = (args.get("kunde_id") or "").upper()
        r = cockpit.send_onboarding(kid)
        return {"ok": True, "text": f"Onboarding-Mail {kid}: {r}", "raw": r}
    if name == "meeting_scan":
        r = sales.meeting_scan(
            db,
            website=args.get("website") or "",
            email=args.get("email") or "",
            firma=args.get("firma") or "",
            kontakt=args.get("kontakt") or "",
            phone=args.get("phone") or "",
            note=args.get("note") or "",
        )
        return {
            "ok": bool(r.get("ok")),
            "text": r.get("text") or r.get("error") or "Scan fertig.",
            "raw": r,
            "deal_id": r.get("deal_id"),
        }
    if name == "sales_invite":
        r = sales.invite(
            db,
            email=args.get("email") or "",
            firma=args.get("firma") or "",
            phone=args.get("phone") or "",
            website=args.get("website") or "",
            send_email=True,
        )
        return {"ok": bool(r.get("ok", True)), "text": json.dumps(r, ensure_ascii=False)[:1200], "raw": r}
    if name == "sales_freigabe":
        r = sales.freigabe(
            db,
            args.get("deal_id") or "",
            action=args.get("decision") or args.get("action") or "send_pain",
        )
        return {"ok": bool(r.get("ok", True)), "text": json.dumps(r, ensure_ascii=False)[:1200], "raw": r}
    if name == "help":
        catalog = ""
        inv = ""
        if _nils_tools is not None:
            catalog = "\n\n" + _nils_tools.catalog_for_prompt(compact=True)
        try:
            import nils_inventory as inventory

            inv = "\n\n" + inventory.status_for_christian()
        except Exception:
            pass
        return {
            "ok": True,
            "text": (
                "Hey, ich bin Nils. Schreib einfach normal, ich greife selbst zu den Werkzeugen.\n"
                "Research, Status, Entwürfe, Cursor-Code nach Freigabe.\n"
                "„inventar“ = was ich gerade live habe."
                + inv
                + catalog
            ),
        }
    if name == "web_context":
        import llm_web

        ctx = llm_web.gather_context(args.get("query") or args.get("text") or "")
        return {"ok": bool(ctx), "text": ctx or "Keine Live-Fakten gefunden."}
    if name == "register_lookup":
        import sys
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from akquise import register as reg

        person = (args.get("person") or "").strip()
        company = (args.get("company") or "").strip()
        city = (args.get("city") or "").strip()
        if person:
            r = reg.lookup_person(person)
            if r.get("found") and r.get("holdings"):
                lines = [f"Person: {r.get('person_name') or person}", "Mandate/Firmen:"]
                for h in r["holdings"][:15]:
                    lines.append(f"• {h.get('name')} ({h.get('role') or '–'}) {h.get('city') or ''}".strip())
                return {"ok": True, "text": "\n".join(lines), "raw": r}
            if r.get("northdata_url"):
                return {
                    "ok": False,
                    "text": (
                        f"Kein API-Key für Personen-Lookup. "
                        f"Northdata-Link: {r.get('northdata_url')}\n"
                        f"{r.get('hint') or ''}"
                    ),
                    "raw": r,
                }
            return {"ok": False, "text": r.get("error") or "Nichts gefunden.", "raw": r}
        if company:
            r = reg.lookup_company(company, city)
            if r.get("found"):
                lines = [
                    f"Firma: {r.get('company_name')}",
                    f"Register: {r.get('register_id') or '–'} {r.get('register_court') or ''}".strip(),
                    f"Quelle: {r.get('source')}",
                ]
                if r.get("managers"):
                    lines.append("GF: " + ", ".join(r["managers"]))
                if r.get("openregister_url") or r.get("northdata_url"):
                    lines.append(r.get("openregister_url") or r.get("northdata_url"))
                return {"ok": True, "text": "\n".join(lines), "raw": r}
            return {
                "ok": False,
                "text": (
                    (r.get("hint") or "Kein Treffer.")
                    + ("\n" + (r.get("northdata_url") or "") if r.get("northdata_url") else "")
                ),
                "raw": r,
            }
        return {"ok": False, "error": "person oder company nötig"}
    if _nils_tools is not None:
        extra = _nils_tools.execute_extra(db, name, args)
        if extra is not None:
            return extra
    return {"ok": False, "error": f"Unbekanntes Tool: {name}"}


def match_fast_tools(text: str) -> list[dict[str, Any]]:
    """Deterministische Shortcuts ohne LLM."""
    t = _norm(text)
    tools: list[dict[str, Any]] = []
    if t in ("hilfe", "help", "?", "was kannst du", "/help"):
        tools.append({"name": "help", "args": {}})
        return tools
    if t in (
        "tools",
        "werkzeuge",
        "katalog",
        "was kannst du alles",
        "/tools",
        "inventory",
        "inventar",
        "was hast du",
        "was kannst du alles",
    ):
        tools.append({"name": "inventory", "args": {}})
        return tools
    if t in ("orchestrator", "orchester", "chef hirn", "chef-hirn", "mitarbeiter status"):
        tools.append({"name": "orchestrate", "args": {}})
        return tools
    if any(x in t for x in ("alle kunden", "kundenliste", "liste kunden")):
        tools.append({"name": "list_kunden", "args": {}})
    m = KID_RE.search(text or "")
    if m and any(x in t for x in ("status", "stand", "info", "kunde", "fortschritt")):
        tools.append({"name": "kunde_status", "args": {"kunde_id": m.group(1).upper()}})
    elif m and not tools:
        tools.append({"name": "kunde_status", "args": {"kunde_id": m.group(1).upper()}})
    if any(x in t for x in ("dual", "server status", "infra", "n8n status")):
        tools.append({"name": "dual_status", "args": {}})
    if "guardian" in t or "wächter" in t or "waechter" in t:
        tools.append({"name": "guardian", "args": {}})
    if any(x in t for x in ("radar", "trend scout", "trend-scout")):
        tools.append({"name": "radar_status", "args": {}})
    if any(x in t for x in ("akquise queue", "buy queue", "akquise-liste", "buyer queue")):
        tools.append({"name": "akquise_queue", "args": {}})
    if any(x in t for x in ("deals", "funnel", "pipeline", "sales deals")):
        tools.append({"name": "sales_deals", "args": {}})
    # Golfclub-Text (German Golf Guide)
    if any(x in t for x in ("golfclub", "golf club", "dgv", "golf guide text", "club-text", "club text")):
        m_dgv = re.search(r"\bdgv\s*[#:]?\s*(\d{3,6})\b", text or "", re.I)
        if not m_dgv:
            m_dgv = re.search(r"\b(\d{4,6})\b", text or "")
        m_club = re.search(
            r"(?:club|golfclub)\s+([A-ZÄÖÜ][\wÄÖÜäöüß &\-]{2,40})",
            text or "",
            re.I,
        )
        tools.append(
            {
                "name": "golf_club_text",
                "args": {
                    "dgv": m_dgv.group(1) if m_dgv else "",
                    "club": m_club.group(1).strip() if m_club else "",
                    "extra": (text or "")[:400],
                },
            }
        )
    # Instagram Caption (ohne Upload)
    if any(x in t for x in ("instagram caption", "insta caption", "caption für", "ig caption")) or (
        "instagram" in t and any(x in t for x in ("text", "caption", "posting text", "schreib"))
        and "generier" not in t
        and "bild" not in t
    ):
        brand = "German Golf Guide" if "golf" in t else "Webschmiede"
        tools.append({"name": "instagram_caption", "args": {"topic": text or "", "brand": brand}})
    # Dokument-Entwürfe
    if any(x in t for x in ("rechnung entwurf", "entwurf rechnung", "schreib rechnung", "rechnung schreiben")):
        tools.append({"name": "draft_document", "args": {"kind": "rechnung", "details": text or ""}})
    elif any(x in t for x in ("angebot entwurf", "entwurf angebot", "schreib angebot")) and "senden" not in t:
        tools.append({"name": "draft_document", "args": {"kind": "angebot", "details": text or ""}})
    elif any(x in t for x in ("onboarding entwurf", "onboarding text", "onboarding checkliste")):
        tools.append({"name": "draft_document", "args": {"kind": "onboarding", "details": text or ""}})
    elif any(x in t for x in ("dashboard briefing", "dashboard entwurf", "dashboard planen")):
        tools.append({"name": "draft_document", "args": {"kind": "dashboard", "details": text or ""}})
    # Website-Template (nur Entwurf ohne Coding-Agent)
    if any(x in t for x in ("website template", "html template", "landing template")) and not any(
        x in t for x in ("programmier", "cursor", "im repo")
    ):
        ent_w = extract_meeting_entities(text or "")
        tools.append(
            {
                "name": "website_template",
                "args": {
                    "name": ent_w.get("firma") or "Kunde",
                    "notes": (text or "")[:500],
                },
            }
        )
    # Cursor Cloud Agent (1:1 wie IDE) – Freigabe nötig
    try:
        import nils_cursor_bridge as _bridge

        if _bridge.looks_like_coding_task(text or "") or t.startswith("cursor:"):
            tools.append({"name": "cursor_code", "args": {"task": text or ""}})
    except Exception:
        pass
    if any(x in t for x in ("cursor status", "cursor bridge", "cursor job")):
        m_job = re.search(r"\b(cj_\w+)\b", text or "", re.I)
        tools.append({"name": "cursor_status", "args": {"job_id": m_job.group(1) if m_job else ""}})
    # Reiner Website-Scrape (ohne vollständigen Meeting-Scan)
    if any(x in t for x in ("scrape", "website crawlen", "seite auslesen", "website auslesen")):
        urls0 = URL_RE.findall(text or "")
        ent_s = extract_meeting_entities(text or "")
        u = urls0[0] if urls0 else ent_s.get("website") or ""
        if u:
            tools.append({"name": "scrape_website", "args": {"url": u}})
    # Live-Fakten / Deep Research (Inventar steuert mit)
    try:
        import llm_web
        import nils_inventory as inv
        import nils_research as research

        reach = inv.suggest_reach(text or "")
        if "deep_research" in reach or research.looks_like_research(text or ""):
            tools.append({"name": "deep_research", "args": {"query": text}})
        elif "web" in reach or llm_web.needs_live_facts(text or ""):
            tools.append({"name": "web_context", "args": {"query": text}})
    except Exception:
        try:
            import llm_web
            import nils_research as research

            if research.looks_like_research(text or ""):
                tools.append({"name": "deep_research", "args": {"query": text}})
            elif llm_web.needs_live_facts(text or ""):
                tools.append({"name": "web_context", "args": {"query": text}})
        except Exception:
            pass
    # Handelsregister / Personen
    if any(
        x in t
        for x in (
            "handelsregister",
            "geschäftsführer",
            "geschaeftsfuehrer",
            "holding",
            "northdata",
            "openregister",
            "firmen von",
            "wie viele firmen",
            "mandate",
        )
    ) or ("gmbh" in t and any(x in t for x in ("gf", "geschäft", "recherch", "analys"))):
        m_pers = re.search(
            r"(?:geschäftsführer|geschaeftsfuehrer|person|über|zu)\s+([A-ZÄÖÜ][\w\-]+(?:\s+[A-ZÄÖÜ][\w\-]+)+)",
            text or "",
        )
        if not m_pers:
            m_pers = re.search(r"\b([A-ZÄÖÜ][a-zäöüß]+\s+[A-ZÄÖÜ][a-zäöüß]+)\b", text or "")
        if m_pers and "gmbh" not in m_pers.group(1).lower():
            tools.append({"name": "register_lookup", "args": {"person": m_pers.group(1).strip()}})
        else:
            ent0 = extract_meeting_entities(text or "")
            co = ent0.get("firma") or ""
            if not co:
                m_co = re.search(
                    r"([A-ZÄÖÜ][\wÄÖÜäöüß &\-]{2,50}(?:GmbH|UG|AG))",
                    text or "",
                )
                if m_co:
                    co = m_co.group(1).strip()
            if co:
                tools.append({"name": "register_lookup", "args": {"company": co}})
    ent = extract_meeting_entities(text or "")
    scan_words = (
        "scan", "scann", "analys", "recherch", "firma prüfen", "firma pruefen",
        "angebot", "einschätz", "einschaetz", "meeting", "kunde vor ort",
        "check die firma", "schau dir", "website anschauen",
    )
    want_scan = any(x in t for x in scan_words) or (
        bool(ent.get("website")) and bool(ent.get("email"))
    )
    if want_scan and (ent.get("website") or ent.get("firma")):
        tools.append(
            {
                "name": "meeting_scan",
                "args": {
                    "website": ent.get("website") or "",
                    "email": ent.get("email") or "",
                    "firma": ent.get("firma") or "",
                    "note": (text or "")[:400],
                },
            }
        )
        return tools

    urls = URL_RE.findall(text or "")
    if urls and any(x in t for x in ("ship", "freigabe check", "link prüfen", "link pruefen")):
        tools.append({"name": "shipcheck", "args": {"url": urls[0]}})
    if any(x in t for x in ("ux check", "ux-gate", "fact-gate", "ux gate")):
        target = urls[0] if urls else ""
        if not target:
            parts = (text or "").split(None, 2)
            target = parts[2] if len(parts) >= 3 else ""
        tools.append({"name": "ux_gate", "args": {"url": target, "path": target, "text": target}})
    # Angebot senden (bestehender Kunde)
    if m and "angebot" in t and any(x in t for x in ("senden", "schick", "mail")):
        pkg = "pro" if "pro" in t else "starter"
        tools.append({"name": "send_offer", "args": {"kunde_id": m.group(1).upper(), "package": pkg}})
    if m and "onboarding" in t and any(x in t for x in ("senden", "schick", "mail")):
        tools.append({"name": "send_onboarding", "args": {"kunde_id": m.group(1).upper()}})
    # Einladung nach Scan
    if any(x in t for x in ("einladung senden", "invite senden", "wizard schicken")) and ent.get("email"):
        tools.append(
            {
                "name": "sales_invite",
                "args": {
                    "email": ent["email"],
                    "firma": ent.get("firma") or "",
                    "website": ent.get("website") or "",
                },
            }
        )
    return tools


def _looks_like_ops(text: str) -> bool:
    t = _norm(text)
    if KID_RE.search(text or ""):
        return True
    ops = (
        "alle kunden",
        "kundenliste",
        "guardian",
        "dual",
        "shipcheck",
        "freigabe",
        "onboarding",
        "angebot senden",
        "meeting",
        "scann",
        "scan die",
        "radar",
        "workorder",
        "auftrag",
        "tisch-promo",
        "tisch promo",
        "golfclub",
        "dgv",
        "instagram caption",
        "scrape",
        "website template",
        "programmier",
        "cursor",
        "baue website",
        "baue dashboard",
        "tools",
    )
    return any(x in t for x in ops)


def _build_companion_messages(
    message: str,
    tool_notes: list[str],
    history: list[dict],
    *,
    from_voice: bool = False,
    memory_block: str = "",
) -> list[dict]:
    import human_voice as voice
    import telegram_session as tg_sess

    voice_hint = ""
    if from_voice:
        voice_hint = (
            " Christian hat gesprochen (Sprachnachricht). Das Transkript kann Hörfehler haben. "
            "Wenn etwas unsinnig oder falsch klingt: korrigiere höflich im normalen Text, "
            "z.B. „Meinst du eher …?“ und antworte dann auf die vermutlich gemeinte Sache. "
            "Nie mit „(verstanden: …)“ oder einer Transkript-Übersicht anfangen. Einfach normal schreiben."
        )
    system = voice.nils_system(
        " Telegram mit Christian. Du bist Nils, nicht Christian. "
        "Du kennst deinen Werkzeugkasten (unten) und greifst selbst danach, "
        "wenn Fakten, Research, Status oder Code nötig sind. Christian muss Tools nicht nennen. "
        "Ideen sammeln = Text. Bild nur bei „generiere jetzt …“. "
        "Gedächtnis ist dauerhaft. Freigabe bei Mail/Cursor/Bild. "
        "Keine erfundenen Fakten. Keine Minutenversprechen. "
        "Cursor-Level: führen, dann freigeben lassen."
        + voice_hint,
        fast=False,
    )
    chunks = []
    try:
        import nils_inventory as inv

        chunks.append(inv.for_prompt(compact=True))
    except Exception:
        pass
    try:
        import nils_ux_gate as ux

        chunks.append(ux.policy_for_prompt(short=True))
    except Exception:
        pass
    try:
        import nils_guided as guided

        chunks.append(guided.guided_policy(short=True))
    except Exception:
        pass
    if memory_block:
        chunks.append(memory_block)
    if tool_notes:
        chunks.append("\n\n".join(tool_notes)[:2800])
    try:
        import nils_truth as truth

        grounded = truth.grounding_block(
            memory=memory_block or "",
            tool_notes=tool_notes or [],
            plan_header="",
            extra="",
        )
        # Quellen + Inventar behalten
        inv_part = chunks[0] if chunks and "WERKZEUGKASTEN" in chunks[0] else ""
        chunks = ([inv_part] if inv_part else []) + [grounded]
    except Exception:
        pass
    ctx = "\n\n".join(c for c in chunks if c)
    user = message[:2000]
    if from_voice:
        prefix = (
            "Sprachnachricht (Transkript, ggf. mit Hörfehlern):\n"
            f"{user}\n\n"
            "Wenn das Transkript danebenliegt: kurz korrigieren, dann normal antworten."
        )
        if ctx:
            prefix = f"{ctx}\n\n{prefix}"
        return tg_sess.build_llm_messages(
            system=system,
            user_text=user,
            history=history,
            history_limit=10,
            user_prefix=prefix,
        )
    prefix = "Nachricht von Christian:"
    if ctx:
        prefix = f"{ctx}\n\n{prefix}"
    return tg_sess.build_llm_messages(
        system=system,
        user_text=user,
        history=history,
        history_limit=10,
        user_prefix=prefix,
    )


def _llm_companion(
    message: str,
    tool_notes: list[str],
    history: list[dict],
    *,
    from_voice: bool = False,
    memory_block: str = "",
) -> str:
    """Plauder-/Ideen-Pfad: ein LLM-Call, menschlich, bei Bedarf ausführlich."""
    messages = _build_companion_messages(
        message, tool_notes, history, from_voice=from_voice, memory_block=memory_block
    )
    result = llm.chat(messages, max_tokens=900, temperature=0.7, timeout=55, route="A")
    if result.get("ok") and result.get("reply"):
        return result["reply"].strip()
    return (
        "Kurz hängt mein Hirn. Versuch in einer Minute nochmal, "
        "oder schreib „hilfe“ für die Kurzbefehle."
    )


def _llm_plan(message: str, force_agent: str | None, history: list[dict]) -> dict[str, Any]:
    """LLM plant Tools + Antwortentwurf (JSON)."""
    if _nils_tools is not None:
        catalog = _nils_tools.catalog_for_prompt(compact=True)
    else:
        catalog = (
            "Tools: help, list_kunden, kunde_status, sales_deals, dual_status, "
            "guardian, shipcheck, brain, web_context, register_lookup, meeting_scan, "
            "send_offer, send_onboarding, sales_invite, sales_freigabe."
        )
    import human_voice as voice

    system = (
        voice.DISPATCHER_VOICE
        + "Christian ist der Chef. Plane maximal 3 Tools. "
        "Website scrapen → scrape_website oder meeting_scan. "
        "Golfclub/DGV → golf_club_text. Instagram Text → instagram_caption "
        "(Publish nur mit Freigabe, oft noch Stub). "
        "Angebot/Rechnung/Onboarding-Entwurf → draft_document. "
        "Website/App PROGRAMMIEREN wie in Cursor → cursor_code [FREIGABE]. "
        "Nur HTML-Entwurf ohne Repo → website_template. "
        "Kundenmail → send_mail [FREIGABE]. "
        "Erfinde keine Tool-Outputs. Unklar → weniger Tools, mehr fragen. "
        "Nur JSON:\n"
        '{"say":"kurze menschliche Zwischennotiz","tools":[{"name":"...","args":{}}],'
        '"force_agent":"nils|stefan|null","chat":true}\n'
        "Nur plaudern: tools=[], chat=true, say=Antwort wie Nils.\n"
        f"{catalog}"
    )
    import telegram_session as tg_sess

    hint = f"[force_agent={force_agent}] " if force_agent else ""
    messages = tg_sess.build_llm_messages(
        system=system,
        user_text=hint + message[:3000],
        history=[{**h, "body": (h.get("body") or "")[:800]} for h in (history or [])],
        history_limit=6,
    )
    # Planung/JSON = Route A (schnell, billig)
    result = llm.chat(messages, max_tokens=280, temperature=0.3, timeout=45, route="A")
    if not result.get("ok"):
        return {"say": None, "tools": [], "chat": True, "error": result.get("error")}
    raw = (result.get("reply") or "").strip()
    # extract JSON
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(raw[start : end + 1])
            if isinstance(data, dict):
                data["_provider"] = result.get("provider")
                data["_route"] = result.get("route")
                return data
        except Exception:
            pass
    return {
        "say": raw,
        "tools": [],
        "chat": True,
        "force_agent": force_agent,
        "_provider": result.get("provider"),
        "_route": result.get("route"),
    }


def _llm_finalize(
    message: str,
    tool_notes: list[str],
    force_agent: str | None,
    history: list[dict],
    *,
    from_voice: bool = False,
    memory_block: str = "",
) -> str:
    import human_voice as voice
    import telegram_session as tg_sess

    who = force_agent or "nils"
    voice_hint = ""
    if from_voice:
        voice_hint = (
            " Sprachnachricht: Transkript kann Hörfehler haben. "
            "Bei Unsinn höflich korrigieren („Meinst du eher …?“), dann normal antworten. "
            "Kein „(verstanden: …)“-Vorspann."
        )
    if who == "stefan":
        system = voice.stefan_system(
            "Christian schreibt per Telegram. "
            "Nutze Tool-Ergebnisse und Langzeitgedächtnis als Fakten, nichts erfinden. "
            "Sag klar den nächsten Schritt. Kein Repo-Code ändern."
            + voice_hint
        )
    else:
        system = voice.nils_system(
            "Christian schreibt per Telegram. "
            "Nutze Tool-Ergebnisse und Langzeitgedächtnis als Fakten, nichts erfinden. "
            "Wenn Freigabe nötig ist, frag einfach. "
            "Kein Repo-Code ändern, das macht Cursor. "
            "Klinge wie ein echter Mensch, nicht wie ein Bot. "
            "Schreib frei und mit Substanz wenn’s gebraucht wird."
            + voice_hint
        )

    chunks = []
    try:
        import nils_truth as truth

        chunks.append(
            truth.grounding_block(
                memory=memory_block or "",
                tool_notes=tool_notes or [],
            )
        )
    except Exception:
        if memory_block:
            chunks.append(memory_block)
        if tool_notes:
            chunks.append("Tool-Ergebnisse:\n" + "\n\n".join(tool_notes)[:5500])
    ctx = "\n\n".join(chunks) if chunks else "(keine Extra-Fakten)"
    user_body = f"{ctx}\n\nAufgabe/Frage von Christian:\n{message[:3500]}"
    if from_voice:
        user_body = "Christian hat gesprochen. Transkript ggf. fehlerhaft.\n\n" + user_body
    messages = tg_sess.build_llm_messages(
        system=system,
        user_text=user_body,
        history=[{**h, "body": (h.get("body") or "")[:600]} for h in (history or [])],
        history_limit=10,
    )
    fin_route = "B" if len(ctx) > 1800 else "A"
    result = llm.chat(messages, max_tokens=900, temperature=0.65, timeout=70, route=fin_route)
    if result.get("ok") and result.get("reply"):
        reply = result["reply"].strip()
        try:
            import nils_truth as truth

            if truth.soft_hallucination_flags(reply):
                reply += (
                    "\n\n(Selbstcheck: klingt nach unbelegter Aktion. "
                    "Gilt nur, was Tools wirklich geliefert haben.)"
                )
            reply += truth.honesty_footer(
                had_tools=bool(tool_notes),
                had_web=any("Live-Suche" in (n or "") or "Web-Recherche" in (n or "") for n in (tool_notes or [])),
            )
        except Exception:
            pass
        try:
            import nils_ux_gate as ux

            reply = ux.soft_warn_if_done_without_gate(reply)
        except Exception:
            pass
        return reply
    if tool_notes:
        return tool_notes[0][:3500]
    return "Hirn kurz stumm. Nochmal versuchen oder „hilfe“."


def handle(
    db: sqlite3.Connection,
    text: str,
    *,
    history: list[dict] | None = None,
    pending: dict | None = None,
    from_voice: bool = False,
    media_notes: list[str] | None = None,
    memory_block: str = "",
) -> dict[str, Any]:
    history = history or []
    media_notes = media_notes or []
    tnorm = _norm(text)

    # Confirm pending risky tool / paid media / discovery
    if pending and pending.get("tool"):
        # Discovery: Freigabe oder Nachschärfen
        if pending.get("phase") == "discovery" or pending.get("tool") == "discovery":
            import nils_guided as guided

            task0 = (pending.get("task") or (pending.get("args") or {}).get("task") or "").strip()
            intent = (pending.get("intent") or guided.classify_intent(task0)).strip()
            if guided.is_go_confirm(text) or tnorm in YES:
                # Bau → Cursor
                if intent == "build" or guided.classify_intent(task0) == "build":
                    out = execute_tool(
                        db,
                        "cursor_code",
                        {"task": task0},
                        confirmed=True,
                    )
                    return {
                        "reply": out.get("text") or out.get("error") or "Gestartet.",
                        "pending": None,
                        "needs_confirm": False,
                        "route": "guided_go_build",
                        "tools": ["cursor_code"],
                    }
                # Sonst: freigegeben → Companion mit Execute-Haltung + passende Tools
                notes: list[str] = [
                    guided.execute_after_go_system(intent),
                    f"Freigegebener Auftrag:\n{task0[:2500]}",
                ]
                tools_go = match_fast_tools(task0)
                # Kein zweites Guided; Risk-Tools hier nur wenn schon freigegeben und sinnvoll
                for t in tools_go[:3]:
                    name = t.get("name")
                    if name in ("cursor_code",):
                        continue
                    if name in RISKY:
                        out = execute_tool(db, name, t.get("args") or {}, confirmed=True)
                    else:
                        out = execute_tool(db, name, t.get("args") or {}, confirmed=False)
                    if out.get("text"):
                        notes.append(out["text"])
                    elif out.get("error"):
                        notes.append(str(out["error"]))
                messages = _build_companion_messages(
                    task0,
                    notes,
                    history,
                    from_voice=from_voice,
                    memory_block=memory_block,
                )
                # Override system flavor via first note already in tool_notes
                return {
                    "reply": "",
                    "pending": None,
                    "needs_confirm": False,
                    "route": "guided_go_work",
                    "tools": [t.get("name") for t in tools_go],
                    "stream_messages": messages,
                }
            if tnorm in NO:
                return {
                    "reply": "Ok, gestoppt. Sag Bescheid wenn wir’s anders angehen.",
                    "pending": None,
                    "needs_confirm": False,
                    "route": "guided_cancel",
                }
            merged = guided.merge_task_after_answers(task0, text)
            return {
                "reply": (
                    "Passt, hab’s mit reingenommen.\n"
                    "Wenn wir so weitermachen sollen: „mach das“. Sonst noch was ergänzen."
                ),
                "pending": {
                    "phase": "discovery",
                    "tool": "discovery",
                    "task": merged,
                    "intent": intent,
                },
                "needs_confirm": True,
                "route": "guided_refine",
            }

        if tnorm in YES:
            if pending.get("tool") == "paid_image":
                import nils_ops as nils_ops_svc

                prompt = (pending.get("args") or {}).get("text") or ""
                creative = nils_ops_svc.try_creative_generation(db, prompt, confirmed=True)
                return {
                    "reply": (creative or {}).get("reply") or "Bild fertig.",
                    "pending": None,
                    "needs_confirm": False,
                    "route": "paid_image_confirm",
                    "tools": ["requesty_image"],
                    "generated": (creative or {}).get("generated") or [],
                    "creative": (creative or {}).get("creative"),
                    "llm_model": (creative or {}).get("llm_model"),
                }
            out = execute_tool(db, pending["tool"], pending.get("args") or {}, confirmed=True)
            return {
                "reply": out.get("text") or out.get("error") or "Erledigt.",
                "pending": None,
                "needs_confirm": False,
                "route": "confirm",
                "tools": [pending["tool"]],
            }
        if tnorm in NO:
            return {"reply": "Abgebrochen. Kein Geld ausgegeben.", "pending": None, "needs_confirm": False, "route": "cancel"}
        return {
            "reply": "Noch offen: „ja“ zum Ausführen oder „abbrechen“.",
            "pending": pending,
            "needs_confirm": True,
            "route": "confirm_wait",
        }

    force, msg = parse_force_agent(text)

    # Budget / Kostenstatus
    if _norm(msg) in ("budget", "kosten", "spend", "limits", "limit"):
        try:
            import requesty_client as rq

            return {
                "reply": rq.spend_status_text(),
                "pending": None,
                "needs_confirm": False,
                "route": "budget",
                "tools": [],
            }
        except Exception:
            pass

    if _norm(msg) in ("tagesreport", "tages report", "daily report", "server report"):
        try:
            import nils_daily_report as dr

            data = dr.send_report(mail=False, telegram=False)
            return {
                "reply": (data.get("report") or {}).get("text") or "Report leer.",
                "pending": None,
                "needs_confirm": False,
                "route": "daily_report",
                "tools": [],
            }
        except Exception as e:
            return {
                "reply": f"Tagesreport fehlgeschlagen: {e}",
                "pending": None,
                "needs_confirm": False,
                "route": "daily_report",
                "tools": [],
            }

    if _norm(msg) in ("kostenwächter", "kostenwaechter", "cost sentry", "kosten stop"):
        try:
            import nils_cost_sentry as cs

            r = cs.run(apply=True, notify=False)
            return {
                "reply": r.get("text") or "Kosten-Wächter ok.",
                "pending": None,
                "needs_confirm": False,
                "route": "cost_sentry",
                "tools": [],
            }
        except Exception as e:
            return {
                "reply": f"Kosten-Wächter: {e}",
                "pending": None,
                "needs_confirm": False,
                "route": "cost_sentry",
                "tools": [],
            }

    if _norm(msg) in ("hirnwächter", "hirnwaechter", "brain watch", "night worker", "wächter", "waechter"):
        try:
            import nils_brain_watch as bw

            r = bw.run(notify=False, night=False)
            return {
                "reply": r.get("text") or "Hirn-Wächter ok.",
                "pending": None,
                "needs_confirm": False,
                "route": "brain_watch",
                "tools": [],
            }
        except Exception as e:
            return {
                "reply": f"Hirn-Wächter: {e}",
                "pending": None,
                "needs_confirm": False,
                "route": "brain_watch",
                "tools": [],
            }

    # UX / Fact-Gate
    low = _norm(msg)
    if low.startswith("ux check") or low.startswith("ux-gate") or low in ("ux", "ux gate", "fact gate"):
        target = (msg or "").split(None, 2)
        arg = target[2] if len(target) >= 3 else (target[1] if len(target) == 2 and target[0] == "ux" else "")
        if low in ("ux", "ux gate", "fact gate"):
            arg = ""
        if low.startswith("ux-gate"):
            arg = (msg or "")[len("ux-gate") :].strip()
        try:
            import nils_tools as nt

            out = nt.execute_extra(db, "ux_gate", {"url": arg or "", "path": arg or "", "text": arg or ""})
            return {
                "reply": (out or {}).get("text") or "UX-Gate leer.",
                "pending": None,
                "needs_confirm": False,
                "route": "ux_gate",
                "tools": ["ux_gate"],
            }
        except Exception as e:
            return {
                "reply": f"UX-Gate: {e}",
                "pending": None,
                "needs_confirm": False,
                "route": "ux_gate",
                "tools": [],
            }

    tools = match_fast_tools(msg)

    # Reine Research-Tools → Quellen holen, dann menschlich antworten (kein Plan-Dump)
    _research_only = frozenset(
        {"deep_research", "web_context", "register_lookup", "scrape_website", "meeting_scan"}
    )
    if (
        tools
        and not force
        and all((t.get("name") in _research_only) for t in tools)
        and not any(t.get("name") == "meeting_scan" for t in tools)  # scan hat eigenes Freigabe-Flow
    ):
        notes: list[str] = list(media_notes)
        for t in tools[:3]:
            out = execute_tool(db, t["name"], t.get("args") or {}, confirmed=False)
            if out.get("text"):
                notes.append(out["text"])
            elif out.get("error"):
                notes.append(str(out["error"]))
        messages = _build_companion_messages(
            msg, notes, history, from_voice=from_voice, memory_block=memory_block
        )
        return {
            "reply": "",
            "pending": None,
            "needs_confirm": False,
            "route": "research_companion",
            "tools": [t.get("name") for t in tools],
            "stream_messages": messages,
        }

    # Guided Mode (Cursor-Level): führen vor Aktion (nach Research-Shortcut)
    try:
        import nils_guided as guided

        if guided.needs_guidance(msg, tools) and not guided.skip_guided(msg) and not force:
            d = guided.run_guided(msg)
            if d.get("ok"):
                return {
                    "reply": d.get("text") or "Kurz klären bevor wir loslegen.",
                    "pending": d.get("pending"),
                    "needs_confirm": True,
                    "route": "guided",
                    "tools": ["guided"],
                    "llm_model": d.get("llm_model"),
                }
    except Exception:
        pass

    # Requesty Kreativ: Logo / Bild (nicht wenn schon Text-Tools wie Caption greifen)
    skip_creative = any(
        t.get("name") in (
            "instagram_caption",
            "golf_club_text",
            "draft_document",
            "website_template",
            "list_tools",
            "help",
            "inventory",
            "cursor_code",
            "cursor_status",
        )
        for t in tools
    )
    if not skip_creative:
        try:
            import requesty_client as rq
            import nils_ops as nils_ops_svc

            creative_kind = rq.classify_creative(msg)
            if creative_kind != "text":
                creative = nils_ops_svc.try_creative_generation(db, msg, confirmed=False)
                if creative:
                    return {
                        "reply": creative.get("reply") or "",
                        "pending": creative.get("pending"),
                        "needs_confirm": bool(creative.get("needs_confirm")),
                        "route": "requesty_creative",
                        "tools": ["requesty_image"],
                        "generated": creative.get("generated") or [],
                        "creative": creative.get("creative"),
                        "llm_model": creative.get("llm_model"),
                        "cost": creative.get("cost"),
                    }
        except Exception:
            pass

    # Expliziter Mitarbeiter-Prefix bleibt Force für Orchestrator
    # --- Nils Orchestrator (Chef-Hirn) ---
    try:
        import nils_orchestrator as orch

        if orch.should_orchestrate(msg, force_agent=force, has_tools=bool(tools)):
            # reine Meta-Tools ohne Arbeit → nicht orchestrieren
            only_meta = tools and all(
                t.get("name") in ("help", "list_tools", "cursor_status") for t in tools
            )
            if not only_meta:
                result = orch.run(
                    db,
                    msg,
                    force_agent=force,
                    pre_tools=tools,
                    history=history,
                    memory_block=memory_block,
                    from_voice=from_voice,
                    execute_tools_fn=execute_tool,
                )
                return {
                    "reply": result.get("reply") or "",
                    "pending": result.get("pending"),
                    "needs_confirm": bool(result.get("needs_confirm")),
                    "route": result.get("route") or "orchestrator",
                    "tools": result.get("tools") or ["orchestrator"],
                    "plan": result.get("plan"),
                    "llm_route": result.get("llm_route"),
                    "n8n": result.get("n8n"),
                    "stream_messages": result.get("stream_messages"),
                }
    except Exception:
        pass

    # Expliziter Mitarbeiter → Brain (Fallback ohne Orchestrator)
    if force and force in ("stefan", "nils", "radar", "scout", "anwalt"):
        tools = [{"name": "brain", "args": {"message": msg, "force_agent": force}}] + [
            t for t in tools if t["name"] != "brain"
        ]

    # Schneller Companion-Pfad: Plaudern / Ideen / Research ohne Orchestrator-Dump
    if not tools and not force and (media_notes or not _looks_like_ops(msg)):
        notes: list[str] = list(media_notes)
        try:
            import llm_web
            import nils_research as research

            if research.looks_like_research(msg):
                rr = research.deep_research(msg)
                if rr.get("text"):
                    notes.append(rr["text"])
            elif media_notes or llm_web.needs_live_facts(msg) or ("?" in msg and len(msg) > 20):
                ctx = llm_web.gather_context(msg)
                if ctx:
                    notes.append(ctx)
        except Exception:
            try:
                import llm_web

                if media_notes or llm_web.needs_live_facts(msg) or ("?" in msg and len(msg) > 20):
                    ctx = llm_web.gather_context(msg)
                    if ctx:
                        notes.append(ctx)
            except Exception:
                pass
        messages = _build_companion_messages(
            msg, notes, history, from_voice=from_voice, memory_block=memory_block
        )
        return {
            "reply": "",
            "pending": None,
            "needs_confirm": False,
            "route": "companion",
            "tools": (["media"] if media_notes else [])
            + (["deep_research"] if any("Research-Quellen" in n for n in notes) else [])
            + (
                ["web_context"]
                if any("Web-Recherche" in n or "Wikipedia" in n or "Wetter" in n for n in notes)
                else []
            ),
            "stream_messages": messages,
        }

    plan: dict[str, Any] = {}
    if not tools and not force:
        plan = _llm_plan(msg, force, history)
        for t in plan.get("tools") or []:
            if isinstance(t, dict) and t.get("name"):
                tools.append({"name": t["name"], "args": t.get("args") or {}})
        if plan.get("force_agent") and not force:
            force = str(plan.get("force_agent"))
            if force in ("stefan", "nils", "radar", "scout", "anwalt"):
                tools.insert(0, {"name": "brain", "args": {"message": msg, "force_agent": force}})

    # Default: bei freiem Text ohne Tools → Brain Nils + Chat
    if not tools:
        if plan.get("say") and plan.get("chat") and not force:
            return {
                "reply": plan["say"],
                "pending": None,
                "needs_confirm": False,
                "route": "chat",
                "provider": plan.get("_provider"),
            }
        tools = [{"name": "brain", "args": {"message": msg, "force_agent": force or "nils"}}]

    notes: list[str] = []
    pending_out = None
    ran: list[str] = []
    scan_raw: dict[str, Any] | None = None
    for t in tools[:4]:
        name = t["name"]
        args = t.get("args") or {}
        if name == "brain" and not args.get("message"):
            args["message"] = msg
        if name == "brain" and force and not args.get("force_agent"):
            args["force_agent"] = force
        out = execute_tool(db, name, args, confirmed=False)
        ran.append(name)
        if out.get("needs_confirm"):
            pending_out = out.get("pending")
            notes.append(out.get("text") or "Bestätigung nötig.")
            break
        if out.get("text"):
            notes.append(f"[{name}]\n{out['text']}")
        elif out.get("error"):
            notes.append(f"[{name}] Fehler: {out['error']}")
        if name == "meeting_scan" and out.get("ok"):
            scan_raw = out.get("raw") if isinstance(out.get("raw"), dict) else None

    # Nach Meeting-Scan: Einladung nur mit „ja“
    if scan_raw and scan_raw.get("email") and not pending_out:
        pending_out = {
            "tool": "sales_invite",
            "args": {
                "email": scan_raw.get("email"),
                "firma": scan_raw.get("firma") or "",
                "website": scan_raw.get("website") or "",
            },
        }
        notes.append(
            f"Soll ich die Discovery-Einladung jetzt an {scan_raw.get('email')} senden? "
            "Antworte „ja“ oder „abbrechen“."
        )

    if pending_out and ran == ["meeting_scan"]:
        # Scan-Ergebnis + Freigabe-Frage, ohne zweiten LLM-Roundtrip
        return {
            "reply": "\n\n".join(notes)[:3900],
            "pending": pending_out,
            "needs_confirm": True,
            "route": "meeting_scan",
            "tools": ran,
        }

    if pending_out:
        return {
            "reply": notes[0] if notes else "Bestätigung nötig: ja / abbrechen.",
            "pending": pending_out,
            "needs_confirm": True,
            "route": "tools",
            "tools": ran,
        }

    # Reine Hilfe / reiner Scan ohne Mail / nur Live-Fakten
    if ran in (["help"], ["meeting_scan"]) and notes:
        return {
            "reply": "\n\n".join(notes)[:3900],
            "pending": None,
            "needs_confirm": False,
            "route": ran[0],
            "tools": ran,
        }
    if ran == ["web_context"] and notes:
        reply = _llm_companion(
            msg, notes, history, from_voice=from_voice, memory_block=memory_block
        )
        return {
            "reply": reply,
            "pending": None,
            "needs_confirm": False,
            "route": "companion",
            "tools": ran,
        }

    reply = _llm_finalize(
        msg, notes, force, history, from_voice=from_voice, memory_block=memory_block
    )
    return {
        "reply": reply,
        "pending": None,
        "needs_confirm": False,
        "route": "agent",
        "tools": ran,
        "force_agent": force,
    }
