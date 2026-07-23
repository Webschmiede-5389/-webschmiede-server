# -*- coding: utf-8 -*-
"""Nils Tool-Hirn: Katalog + Ausführung für Telegram/Voice.

Memory (Jahre) liegt in telegram_memory.py.
Hier: optionale Werkzeuge, die Nils bewusst ansteuern kann.
Risiko-Tools brauchen Freigabe („ja“) über telegram_agent.RISKY.
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("nils_tools")

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TOOL_CATALOG: list[dict[str, Any]] = [
    {
        "name": "inventory",
        "risky": False,
        "cat": "meta",
        "desc": "Live: was Nils hat (Keys, Tools, Stubs). Er greift selbst danach.",
    },
    {
        "name": "orchestrate",
        "risky": False,
        "cat": "meta",
        "desc": "Nils Chef-Hirn: Plan (Team+LLM+n8n+Cursor) und Ausführung.",
        "args": "message?",
    },
    {
        "name": "list_tools",
        "risky": False,
        "cat": "meta",
        "desc": "Zeigt alle installierten Nils-Tools (Hirn-Katalog).",
    },
    {
        "name": "deep_research",
        "risky": False,
        "cat": "research",
        "desc": "Tiefe Recherche: Web, OpenRegister, Google Places, Firecrawl/Crawl.",
        "args": "query|text",
    },
    {
        "name": "web_context",
        "risky": False,
        "cat": "search",
        "desc": "Live-Suche / Wetter / aktuelle Fakten (DDG + Wikipedia).",
        "args": "query",
    },
    {
        "name": "scrape_website",
        "risky": False,
        "cat": "scrape",
        "desc": "Website crawlen und kurz analysieren (Titel, Signale, Kontakt).",
        "args": "url|website",
    },
    {
        "name": "meeting_scan",
        "risky": False,
        "cat": "sales",
        "desc": "Firma scannen + Angebots-Entwurf, ohne Kundenmail.",
        "args": "website,email,firma",
    },
    {
        "name": "register_lookup",
        "risky": False,
        "cat": "research",
        "desc": "Handelsregister / Person / Firma (OpenRegister).",
        "args": "person|company,city?",
    },
    {
        "name": "golf_club_text",
        "risky": False,
        "cat": "golf",
        "desc": "Golfclub-Text für German Golf Guide (DGV-Nr. / Clubname).",
        "args": "dgv?,club?,extra?",
    },
    {
        "name": "instagram_caption",
        "risky": False,
        "cat": "social",
        "desc": "Instagram-Caption (Text). Bild nur über bezahlten Pfad mit Quote+ja. Upload Meta: noch nicht live.",
        "args": "topic|text,brand?",
    },
    {
        "name": "instagram_publish",
        "risky": True,
        "cat": "social",
        "desc": "Instagram/FB Publish. Stub bis Meta Graph Token + Pipeline live.",
        "args": "caption,image_url?",
    },
    {
        "name": "draft_document",
        "risky": False,
        "cat": "docs",
        "desc": "Entwurf: angebot | rechnung | onboarding | dashboard-briefing.",
        "args": "kind,kunde?,details?",
    },
    {
        "name": "website_template",
        "risky": False,
        "cat": "web",
        "desc": "Einfaches HTML-Website-Template (Dunkel/Gold) als Text/Code.",
        "args": "name,branche?,notes?",
    },
    {
        "name": "send_mail",
        "risky": True,
        "cat": "mail",
        "desc": "HTML/Text-Mail an Empfänger (nur nach Freigabe).",
        "args": "to,subject,body",
    },
    {
        "name": "send_offer",
        "risky": True,
        "cat": "sales",
        "desc": "Paket-Angebot an bestehenden Kunden (kunde_id).",
        "args": "kunde_id,package?",
    },
    {
        "name": "send_onboarding",
        "risky": True,
        "cat": "sales",
        "desc": "Onboarding-Mail an Kunden.",
        "args": "kunde_id",
    },
    {
        "name": "cursor_code",
        "risky": True,
        "cat": "cursor",
        "desc": "Cursor Cloud Agent wie im IDE: Website/App/Repo-Änderung (braucht CURSOR_API_KEY + Freigabe).",
        "args": "task|prompt,auto_pr?",
    },
    {
        "name": "cursor_status",
        "risky": False,
        "cat": "cursor",
        "desc": "Status der Cursor-Bridge / laufender Jobs.",
        "args": "job_id?",
    },
    {
        "name": "list_kunden",
        "risky": False,
        "cat": "crm",
        "desc": "Kundenliste kurz.",
    },
    {
        "name": "kunde_status",
        "risky": False,
        "cat": "crm",
        "desc": "Status eines Kunden (SHY001 …).",
        "args": "kunde_id",
    },
    {
        "name": "sales_deals",
        "risky": False,
        "cat": "sales",
        "desc": "Offene Sales-Deals.",
    },
    {
        "name": "akquise_queue",
        "risky": False,
        "cat": "akquise",
        "desc": "Aktuelle Buy-/Akquise-Queue (Kurz).",
    },
    {
        "name": "radar_status",
        "risky": False,
        "cat": "ops",
        "desc": "Trend-Radar Status / Queue.",
    },
    {
        "name": "dual_status",
        "risky": False,
        "cat": "ops",
        "desc": "Web + Auto Server Status.",
    },
    {
        "name": "guardian",
        "risky": False,
        "cat": "ops",
        "desc": "Ops-Guardian Status / Safe-Fix.",
    },
    {
        "name": "shipcheck",
        "risky": False,
        "cat": "ops",
        "desc": "URL freigeben vor Teilen (Shipcheck).",
        "args": "url",
    },
    {
        "name": "ux_gate",
        "risky": False,
        "cat": "ops",
        "desc": "Fact+UX-Gate: HTML/URL Heuristik (Links, viewport, Mobile-Risiken).",
        "args": "url|path",
    },
    {
        "name": "brain",
        "risky": False,
        "cat": "ops",
        "desc": "Agency-Hirn (Nils/Stefan/Radar Route).",
        "args": "message,force_agent?",
    },
]

RISKY_TOOLS = frozenset(t["name"] for t in TOOL_CATALOG if t.get("risky"))


def catalog_for_prompt(*, compact: bool = True) -> str:
    if compact:
        bits = []
        for t in TOOL_CATALOG:
            risk = " [FREIGABE]" if t.get("risky") else ""
            args = f"({t['args']})" if t.get("args") else "()"
            bits.append(f"{t['name']}{args}{risk}")
        return (
            "Installierte Nils-Tools: "
            + ", ".join(bits)
            + ". Meta-Instagram-Upload noch Stub. Code/Repo-Edit = Cursor-Handoff."
        )
    lines = ["Installierte Nils-Tools:"]
    for t in TOOL_CATALOG:
        risk = " · FREIGABE" if t.get("risky") else ""
        lines.append(f"• {t['name']} [{t.get('cat')}]{risk}: {t.get('desc')}")
    return "\n".join(lines)


def _ok(text: str, **extra: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"ok": True, "text": text[:4000]}
    out.update(extra)
    return out


def _fail(text: str, **extra: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"ok": False, "text": text[:2000], "error": text[:400]}
    out.update(extra)
    return out


def _tool_list_tools(_: dict[str, Any]) -> dict[str, Any]:
    return _ok(catalog_for_prompt(compact=False))


def _tool_inventory(_: dict[str, Any]) -> dict[str, Any]:
    import nils_inventory as inv

    return _ok(inv.status_for_christian() + "\n\n" + inv.for_prompt(compact=True)[:2500])


def _tool_web_context(args: dict[str, Any]) -> dict[str, Any]:
    import llm_web

    ctx = llm_web.gather_context(args.get("query") or args.get("text") or "")
    return _ok(ctx) if ctx else _fail("Keine Live-Fakten gefunden.")


def _tool_deep_research(args: dict[str, Any]) -> dict[str, Any]:
    import nils_research as research

    q = (args.get("query") or args.get("text") or args.get("message") or "").strip()
    r = research.deep_research(q)
    return {
        "ok": bool(r.get("ok")),
        "text": r.get("text") or r.get("error") or "Keine Quellen.",
        "sources": r.get("sources"),
        "errors": r.get("errors"),
    }


def _tool_orchestrate(args: dict[str, Any]) -> dict[str, Any]:
    import nils_orchestrator as orch

    msg = (args.get("message") or args.get("text") or "").strip()
    if not msg:
        return _ok(orch.status_text())
    # Nur Status wenn leer – echte Runs laufen über telegram_agent
    return _ok(orch.status_text() + f"\n\nLetzter Auftragshinweis: {msg[:200]}")


def _tool_scrape_website(args: dict[str, Any]) -> dict[str, Any]:
    url = (args.get("url") or args.get("website") or "").strip()
    if not url:
        return _fail("url/website fehlt")
    try:
        from akquise.enrichment import crawl_website, normalize_url

        nu = normalize_url(url)
        crawled = crawl_website({"website": nu, "name": "", "url": nu}, cfg={}) or {}
        signals = crawled.get("signals") or crawled.get("analysis") or {}
        lines = [
            f"Scrape: {nu}",
            f"Titel: {crawled.get('title') or '–'}",
            f"Mail: {crawled.get('email') or (signals.get('email') if isinstance(signals, dict) else None) or '–'}",
            f"Telefon: {crawled.get('phone') or '–'}",
        ]
        if isinstance(signals, dict) and signals:
            lines.append("Signale: " + json.dumps(signals, ensure_ascii=False)[:900])
        snippet = (crawled.get("text") or crawled.get("snippet") or "")[:600]
        if snippet:
            lines.append("Text: " + snippet)
        if crawled.get("error"):
            lines.append("Hinweis: " + str(crawled.get("error"))[:200])
        return _ok("\n".join(lines), raw=crawled)
    except Exception as e:
        log.exception("scrape_website")
        return _fail(f"Scrape fehlgeschlagen: {e}")


def _tool_golf_club_text(args: dict[str, Any]) -> dict[str, Any]:
    dgv = str(args.get("dgv") or args.get("dgv_nr") or "").strip()
    club = str(args.get("club") or args.get("name") or "").strip()
    extra = str(args.get("extra") or args.get("notes") or "").strip()
    if not dgv and not club:
        return _fail("Brauche DGV-Nummer oder Clubname.")

    live = ""
    try:
        import llm_web

        q = f"Golfclub Deutschland DGV {dgv} {club}".strip()
        live = llm_web.gather_context(q) or ""
    except Exception:
        live = ""

    import llm_client as llm

    system = (
        "Du schreibst Golfclub-Texte für den German Golf Guide. "
        "Deutsch, warm, konkret, kein Marketing-Blabla. "
        "Struktur: Kurzintro, Platz/Lage, Besonderheiten, für wen geeignet, Abschluss. "
        "Keine erfundenen Fakten. Wenn unsicher: klar sagen was fehlt. "
        "HALLUZINATIONS-VERBOT: Keine erfundenen DGV-Daten, Bahnen, Preise."
    )
    user = (
        f"DGV: {dgv or 'unbekannt'}\n"
        f"Club: {club or 'unbekannt'}\n"
        f"Extra: {extra or '–'}\n\n"
        f"Live-Kontext:\n{live[:2500] or 'keine'}"
    )
    r = llm.chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=900,
        temperature=0.55,
        timeout=60,
        route="B",
    )
    if not r.get("ok") or not r.get("reply"):
        return _fail(r.get("error") or "Club-Text konnte nicht erzeugt werden.")
    header = f"Golfclub-Text · DGV {dgv or '–'} · {club or '–'}\n\n"
    return _ok(header + r["reply"].strip(), draft=True, kind="golf_club")


def _tool_instagram_caption(args: dict[str, Any]) -> dict[str, Any]:
    topic = (args.get("topic") or args.get("text") or args.get("caption") or "").strip()
    brand = (args.get("brand") or "German Golf Guide").strip()
    if not topic:
        return _fail("topic/text fehlt")
    import llm_client as llm

    r = llm.chat(
        [
            {
                "role": "system",
                "content": (
                    f"Du schreibst Instagram-Captions für {brand}. "
                    "Deutsch, menschlich, max 5 Hashtags, keine Emoji-Listen. "
                    "Kein Upload, nur Text."
                ),
            },
            {"role": "user", "content": topic[:2000]},
        ],
        max_tokens=280,
        temperature=0.7,
        timeout=45,
        route="A",
    )
    if not r.get("ok"):
        return _fail(r.get("error") or "Caption fehlgeschlagen")
    note = (
        "\n\n(Hinweis: Caption fertig. Bild = „generiere jetzt …“ mit Kostenvoranschlag. "
        "Meta-Upload noch nicht live – ich schicke dir Text zum Copy-Paste.)"
    )
    return _ok((r.get("reply") or "").strip() + note, brand=brand)


def _tool_instagram_publish(args: dict[str, Any]) -> dict[str, Any]:
    return _fail(
        "Instagram-Publish ist noch nicht verdrahtet (Meta Graph Token + Pipeline fehlen). "
        "Ich kann Caption/Bild-Entwurf machen. Upload kommt als nächster Baustein."
    )


def _tool_draft_document(args: dict[str, Any]) -> dict[str, Any]:
    kind = (args.get("kind") or args.get("type") or "angebot").strip().lower()
    kunde = (args.get("kunde") or args.get("kunde_id") or args.get("firma") or "").strip()
    details = (args.get("details") or args.get("note") or args.get("text") or "").strip()
    allowed = {
        "angebot": "Angebot / Kalkulation Webschmiede (Setup + Monats-Ops, ehrlich).",
        "rechnung": "Rechnung Webschmiede (Positionen, Netto/Brutto, Zahlungsziel).",
        "onboarding": "Onboarding-Checkliste + Mail-Text für neuen Kunden.",
        "dashboard": "Briefing für Kunden-Dashboard (Module, Tabs, was live vs. später).",
        "dashboard-briefing": "Briefing für Kunden-Dashboard (Module, Tabs, was live vs. später).",
    }
    if kind not in allowed:
        return _fail("kind: angebot | rechnung | onboarding | dashboard")
    import llm_client as llm

    r = llm.chat(
        [
            {
                "role": "system",
                "content": (
                    "Du bist Nils von Webschmiede. Schreibst Dokument-Entwürfe auf Deutsch, "
                    "menschlich, konkret. Kein GHL. Dunkel/Gold CI nur erwähnen wenn sinnvoll. "
                    "HALLUZINATIONS-VERBOT: Keine erfundenen Preise/Adressen. "
                    "Fehlende Angaben als [Platzhalter]. "
                    f"Dokumenttyp: {allowed[kind]}"
                ),
            },
            {
                "role": "user",
                "content": f"Kunde/Firma: {kunde or '–'}\nDetails: {details or 'Standard-Portal'}",
            },
        ],
        max_tokens=1000,
        temperature=0.45,
        timeout=60,
        route="B",
    )
    if not r.get("ok"):
        return _fail(r.get("error") or "Entwurf fehlgeschlagen")
    return _ok(f"Entwurf ({kind}) für {kunde or '–'}:\n\n" + (r.get("reply") or "").strip(), kind=kind)


def _tool_website_template(args: dict[str, Any]) -> dict[str, Any]:
    name = (args.get("name") or args.get("firma") or "Kundenname").strip()
    branche = (args.get("branche") or "gastro").strip()
    notes = (args.get("notes") or args.get("extra") or "").strip()
    import llm_client as llm

    r = llm.chat(
        [
            {
                "role": "system",
                "content": (
                    "Du erzeugst EIN vollständiges, einfaches HTML-Template (eine Datei) "
                    "für eine lokale Firmen-Landingpage. "
                    "Dunkel (#1a1712) + Gold (#C9A84C), Bunny Fonts (kein Google Fonts), "
                    "kein Inter/Roboto. Hero vollflächig, eine Headline, ein CTA. "
                    "Kein Tracking. Nur HTML+CSS inline. Keine erfundenen Telefonnummern."
                ),
            },
            {
                "role": "user",
                "content": f"Name: {name}\nBranche: {branche}\nNotizen: {notes or '–'}",
            },
        ],
        max_tokens=2200,
        temperature=0.4,
        timeout=90,
        route="B",
    )
    if not r.get("ok"):
        return _fail(r.get("error") or "Template fehlgeschlagen")
    body = (r.get("reply") or "").strip()
    if len(body) > 3200:
        preview = (
            body[:2800]
            + "\n\n… (gekürzt). Sag „schick als Mail an …“ wenn ich den Rest per Mail senden soll."
        )
        return _ok(preview, html=body, truncated=True)
    return _ok(body, html=body)


def _tool_send_mail(args: dict[str, Any]) -> dict[str, Any]:
    to = (args.get("to") or args.get("email") or "").strip()
    subject = (args.get("subject") or "Webschmiede").strip()
    body = (args.get("body") or args.get("text") or args.get("html") or "").strip()
    if not to or "@" not in to:
        return _fail("to (E-Mail) fehlt")
    if not body:
        return _fail("body fehlt")
    try:
        from agency_mail import send_html_email

        html = body if "<" in body else (
            f"<pre style='font-family:sans-serif;white-space:pre-wrap'>{body}</pre>"
        )
        send_html_email(
            to=to,
            subject=subject,
            html=html,
            text=re.sub(r"<[^>]+>", "", body)[:8000],
        )
        return _ok(f"Mail gesendet an {to}: {subject}")
    except Exception as e:
        return _fail(f"Mail fehlgeschlagen: {e}")


def _tool_akquise_queue(args: dict[str, Any]) -> dict[str, Any]:
    try:
        import agency_akquise as aq

        limit = int(args.get("limit") or 12)
        rows = aq.latest_buy_queue(limit=limit) or []
        if not rows:
            return _ok("Akquise-Queue leer oder noch nicht befüllt.")
        lines = []
        for r in rows[:limit]:
            if isinstance(r, dict):
                lines.append(
                    f"• {r.get('name') or r.get('firma') or r.get('id')} · "
                    f"{r.get('city') or ''} · {r.get('label') or r.get('status') or ''}".strip()
                )
            else:
                lines.append(f"• {r}")
        return _ok("Akquise-Queue:\n" + "\n".join(lines))
    except Exception as e:
        return _fail(f"Akquise: {e}")


def _tool_radar_status(_: dict[str, Any]) -> dict[str, Any]:
    try:
        import agency_radar as radar

        st = radar.status() if hasattr(radar, "status") else {}
        return _ok(
            st.get("summary")
            or json.dumps(st, ensure_ascii=False)[:1500]
            or "Radar: kein Status."
        )
    except Exception as e:
        return _fail(f"Radar: {e}")


def _tool_cursor_code(args: dict[str, Any]) -> dict[str, Any]:
    import nils_cursor_bridge as bridge
    import agency_workorders as workorders

    task = (args.get("task") or args.get("prompt") or args.get("text") or "").strip()
    if not task:
        return _fail("task fehlt")
    auto_pr = args.get("auto_pr")
    if auto_pr is None:
        auto_pr = True
    # Workorder immer anlegen (Audit)
    db = args.get("_db")
    wo_id = ""
    if db is not None:
        try:
            created = workorders.create_order(
                db,
                title=(task[:120] or "Cursor-Auftrag"),
                body=task[:4000],
                source="telegram_cursor",
                kind="cursor_agent",
                auto_execute=False,
            )
            wo_id = ((created.get("order") or {}).get("id") or "") if isinstance(created, dict) else ""
        except Exception as e:
            log.warning("workorder for cursor: %s", e)
    if not bridge.enabled():
        return _ok(
            bridge.status_text()
            + f"\n\nAuftrag liegt als Workorder {wo_id or '–'} (Handoff). "
            "Sobald CURSOR_API_KEY da ist, starte ich denselben Auftrag als Cloud-Agent."
        )
    r = bridge.launch_cloud_agent(
        task,
        workorder_id=wo_id,
        auto_create_pr=bool(auto_pr),
        auto_deploy=True,
        notify=True,
    )
    return r if r.get("ok") else _fail(r.get("text") or r.get("error") or "Cursor start fehlgeschlagen")


def _tool_cursor_status(args: dict[str, Any]) -> dict[str, Any]:
    import nils_cursor_bridge as bridge

    jid = str(args.get("job_id") or args.get("id") or "").strip()
    if not jid and not bridge.configured():
        return _ok(bridge.status_text())
    return _ok(bridge.job_status_text(jid))


def _tool_ux_gate(args: dict[str, Any]) -> dict[str, Any]:
    import nils_ux_gate as ux

    target = (
        args.get("url")
        or args.get("path")
        or args.get("file")
        or args.get("query")
        or args.get("text")
        or ""
    ).strip()
    if not target:
        return _ok(ux.status_for_christian() + "\n\n" + ux.policy_for_prompt(short=True))
    if target.startswith("http"):
        scan = ux.scan_url(target)
    else:
        # relative to repo /root/app
        from pathlib import Path

        p = Path(target)
        if not p.is_file():
            for base in (Path("/root/app"), Path(__file__).resolve().parents[2]):
                cand = base / target
                if cand.is_file():
                    p = cand
                    break
        scan = ux.scan_file(p)
    return _ok(ux.format_scan_report(scan), raw=scan)


_EXTRA_HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "list_tools": _tool_list_tools,
    "inventory": _tool_inventory,
    "orchestrate": _tool_orchestrate,
    "web_context": _tool_web_context,
    "deep_research": _tool_deep_research,
    "scrape_website": _tool_scrape_website,
    "golf_club_text": _tool_golf_club_text,
    "instagram_caption": _tool_instagram_caption,
    "instagram_publish": _tool_instagram_publish,
    "draft_document": _tool_draft_document,
    "website_template": _tool_website_template,
    "send_mail": _tool_send_mail,
    "akquise_queue": _tool_akquise_queue,
    "radar_status": _tool_radar_status,
    "cursor_code": _tool_cursor_code,
    "cursor_status": _tool_cursor_status,
    "ux_gate": _tool_ux_gate,
}


def execute_extra(
    db: sqlite3.Connection,
    name: str,
    args: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Führt Tools aus, die in diesem Modul leben. None = unbekannt hier."""
    args = dict(args or {})
    if name == "cursor_code":
        args["_db"] = db
    fn = _EXTRA_HANDLERS.get(name)
    if not fn:
        return None
    try:
        return fn(args)
    except Exception as e:
        log.exception("tool %s", name)
        return _fail(f"Tool {name}: {e}")


def known_tool_names() -> set[str]:
    return {t["name"] for t in TOOL_CATALOG} | set(_EXTRA_HANDLERS)
