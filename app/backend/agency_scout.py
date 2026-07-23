"""Markt-Scout + Outreach-Stratege (Workflow #3/#4) – Suche und Entwuerfe, kein Auto-Spam."""
from __future__ import annotations

from typing import Any

import agency_akquise as akquise

DISCLAIMER = (
    "Scout liefert Kandidaten und Text-Entwuerfe. "
    "Kein automatischer Versand an Leads. Freigabe durch Christian Pflicht."
)

OFFER_DEFAULT = (
    "Eigenes B2B-Portal + n8n-Automation auf Hetzner DE (Nuernberg), "
    "DocuSeal/AVV, optional Zero-Retention. Kein GoHighLevel."
)

OFFER_BAUSTOFF = (
    "30-Tage Standort-Pilot Baustoffhandel: WhatsApp-Bestellentwuerfe zur Freigabe, "
    "Preislisten-Abgleich Einkauf, Reklamations-Vorsortierung. "
    "Server in Nuernberg, kein tiefer ERP-Eingriff zum Start."
)


def _lead_score(item: dict[str, Any]) -> int:
    score = 0
    tier = (item.get("budget_tier") or "").upper()
    if tier == "A":
        score += 40
    elif tier == "B":
        score += 25
    if item.get("phone"):
        score += 15
    if item.get("buy_summary"):
        score += 10
    if item.get("addon_pitch"):
        score += 5
    # High-ticket fit keywords
    blob = " ".join(
        str(item.get(k) or "")
        for k in ("buy_summary", "addon_pitch", "name", "vertical", "roi_label")
    ).lower()
    for kw, pts in (
        ("portal", 8),
        ("bestell", 6),
        ("buchhalt", 6),
        ("website", 4),
        ("digital", 4),
        ("marge", 5),
        ("amazon", 5),
        ("baustoff", 8),
        ("fachhandel", 6),
        ("eurobaustoff", 10),
        ("grosshandel", 6),
    ):
        if kw in blob:
            score += pts
    return score


def _default_offer_for_vertical(vertical: str) -> str:
    v = (vertical or "").lower()
    if "baustoff" in v or "fachhandel" in v or "eurobaustoff" in v:
        return OFFER_BAUSTOFF
    return OFFER_DEFAULT


def outreach_draft(
    lead: dict[str, Any],
    *,
    ticket: str = "5000",
    offer: str = "",
) -> dict[str, Any]:
    """Ein persoenliches Anschreiben (Entwurf)."""
    name = (lead.get("name") or "Firma").strip()
    vertical = (lead.get("vertical") or "Betrieb").strip()
    offer = (offer or _default_offer_for_vertical(vertical)).strip()
    buy = (lead.get("buy_summary") or "").strip()
    pitch = (lead.get("addon_pitch") or "").strip()
    is_baustoff = "baustoff" in vertical.lower() or "fachhandel" in vertical.lower()
    hook = buy or pitch or (
        "im Baustoffhandel haengen WhatsApp-Bestellungen und Preislisten oft noch am Innendienst"
        if is_baustoff
        else f"viele {vertical}-Betriebe verlieren Zeit mit Listen und Tool-Chaos"
    )
    subject = f"Kurze Frage zu {name}"
    if is_baustoff:
        body = (
            f"Guten Tag,\n\n"
            f"ich melde mich wegen {name}. {hook[0].upper() + hook[1:] if hook else hook}.\n\n"
            f"Wir bieten keinen Software-Katalog, sondern einen 30-Tage-Pilot an einem Standort: "
            f"WhatsApp-Bestellungen vorsortieren, Preislisten abgleichen, Reklamationen vorbereiten. "
            f"Ihre Leute geben nur noch frei. Server stehen in Nuernberg.\n\n"
            f"Orientierung: ca. {ticket} EUR netto fuer den Pilot-Setup, danach Monatsmodell wenn es sitzt.\n"
            f"{offer}\n\n"
            f"Passt ein kurzes Gespraech mit dem Niederlassungsleiter?\n\n"
            f"Mit freundlichen Gruessen\n"
            f"Christian Kummetat\n"
            f"Webschmiede / Digitale Handwerkskunst\n"
        )
    else:
        body = (
            f"Guten Tag,\n\n"
            f"ich schreibe Ihnen wegen {name}. {hook[0].upper() + hook[1:] if hook else hook}.\n\n"
            f"Wir bauen dafuer keine fremde SaaS-Kiste, sondern ein eigenes Portal auf unseren "
            f"EU-Servern (Hetzner Deutschland) inklusive Automation im Hintergrund.\n\n"
            f"Orientierung fuer ein solches Projekt: ca. {ticket} EUR netto, je nach Umfang.\n"
            f"Kurz: {offer}\n\n"
            f"Passt Ihnen ein kurzes Gespraech in der naechsten Woche?\n\n"
            f"Mit freundlichen Gruessen\n"
            f"Christian Kummetat\n"
            f"Webschmiede / Digitale Handwerkskunst\n"
        )
    return {
        "to_name": name,
        "vertical": vertical,
        "phone": lead.get("phone") or "",
        "address": lead.get("address") or "",
        "subject": subject,
        "body": body,
        "call_script": lead.get("call_script") or "",
        "auto_send": False,
        "needs_approval": True,
    }


def campaign(
    *,
    vertical: str = "",
    limit: int = 10,
    ticket: str = "5000",
    offer: str = "",
) -> dict[str, Any]:
    """WF3: Top-Leads aus Buy-Queue + Outreach-Entwuerfe. Kein Versand."""
    limit = max(1, min(int(limit or 10), 30))
    ticket = (ticket or "5000").strip()
    vertical = (vertical or "").strip().lower()
    offer = (offer or _default_offer_for_vertical(vertical)).strip()

    queue = akquise.latest_buy_queue(limit=80)
    if vertical:
        queue = [q for q in queue if (q.get("vertical") or "").lower() == vertical]
    ranked = sorted(queue, key=_lead_score, reverse=True)[:limit]

    items: list[dict[str, Any]] = []
    for lead in ranked:
        draft = outreach_draft(lead, ticket=ticket, offer=offer)
        items.append(
            {
                **lead,
                "score": _lead_score(lead),
                "outreach": draft,
                "approval_status": "pending",
            }
        )

    strategy = {
        "ziel": f"High-Ticket-Kandidaten (~{ticket} EUR) fuer Gespraech, nicht Massenmail",
        "kanal": "E-Mail oder Anruf nach Freigabe",
        "tageslimit_empfehlung": "max. 5 personalisierte Kontakte / Tag",
        "naechste_schritte": [
            "Queue lesen und 3–5 Leads markieren (approve)",
            "Entwurf anpassen (menschlicher Ton)",
            "Erst nach OK senden – oder anrufen",
            "Antwort -> Stefan-Schlachtplan + DocuSeal",
        ],
        "akquise_frisch_ziehen": (
            "Lokal/Server: python -m akquise <vertical> (Places-Key noetig). "
            "Danach erneut /api/agency/scout/campaign."
        ),
    }

    markdown_lines = [
        f"# Scout-Kampagne{' · ' + vertical if vertical else ''}",
        f"Leads: {len(items)} | Ticket ~{ticket} EUR",
        "",
        f"## {DISCLAIMER}",
        "",
        "## Strategie",
        f"- Ziel: {strategy['ziel']}",
        f"- Kanal: {strategy['kanal']}",
        f"- Tageslimit: {strategy['tageslimit_empfehlung']}",
        "",
        "## Top-Leads",
    ]
    if not items:
        markdown_lines.append(
            "- Keine buy-ready Leads in den Reports. "
            "Zuerst Akquise-Lauf: `python -m akquise <vertical>`."
        )
    for i, it in enumerate(items, 1):
        markdown_lines += [
            f"### {i}. {it.get('name')} (Score {it['score']}, Tier {it.get('budget_tier')})",
            f"- {it.get('address') or '–'} | Tel: {it.get('phone') or '–'}",
            f"- {it.get('buy_summary') or it.get('addon_pitch') or ''}",
            f"- Betreff: {it['outreach']['subject']}",
            "```",
            it["outreach"]["body"].rstrip(),
            "```",
            "",
        ]
    markdown_lines += [
        "## Freigabe",
        "POST /api/agency/akquise/approvals mit status=approve|skip|call_later",
        "",
        "## Frische Daten",
        strategy["akquise_frisch_ziehen"],
    ]

    return {
        "ok": True,
        "agent": "scout",
        "workflow": 3,
        "mode": "campaign",
        "disclaimer": DISCLAIMER,
        "vertical": vertical or None,
        "ticket": ticket,
        "offer": offer,
        "strategy": strategy,
        "count": len(items),
        "leads": items,
        "markdown": "\n".join(markdown_lines),
        "auto_send": False,
        "next_agents": ["outreach", "texter", "lektor", "stefan"],
        "hinweis": (
            "Outreach-Workflow = Entwuerfe in dieser Antwort. "
            "Versand nur manuell / nach Freigabe."
        ),
    }


def queue_summary(limit: int = 20) -> dict[str, Any]:
    items = akquise.latest_buy_queue(limit=limit)
    by_v: dict[str, int] = {}
    for it in items:
        v = it.get("vertical") or "?"
        by_v[v] = by_v.get(v, 0) + 1
    return {
        "ok": True,
        "agent": "scout",
        "workflow": 3,
        "mode": "queue",
        "count": len(items),
        "by_vertical": by_v,
        "items": items,
        "disclaimer": DISCLAIMER,
        "auto_send": False,
    }
