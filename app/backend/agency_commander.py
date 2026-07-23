"""Solo-Commander Pack: Fulfillment-Kette, Kapazitaet, Tagesbriefing.

Kein Umsatzversprechen. Kein Auto-Send. Christian bleibt Abschluss + finale QA.
Hosting-Wahrheit: Hetzner Nuernberg (nicht Helsinki).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import agency_anwalt as anwalt
import agency_akquise as akquise
import agency_scout as scout
import agency_stefan as stefan

DISCLAIMER = (
    "Operativer Hebel, keine Umsatzgarantie. "
    "KI bereitet vor – Christian schliesst und gibt final frei. "
    "Kein Auto-Send an Kunden. Standort: Hetzner Nuernberg, nicht Helsinki."
)

# Realistische Solo-Grenzen (Orientierung, keine Prognose)
PERSONAL_GATES = [
    "Vertrauensabschluss (Zoom/Telefon) – kein Bot unterschreibt 5–10k fuer den Kunden",
    "Finale strategische Abnahme Portal/Dashboard vor Go-Live",
    "Freigabe Outreach/Mails und DocuSeal-Versand",
    "Preis/Scope muendlich bestaetigen",
]


def capacity_plan(
    *,
    ticket: float = 5000.0,
    target_month: float = 30000.0,
    hours_week_sales: float = 10.0,
    parallel_active: int = 3,
) -> dict[str, Any]:
    """Ehrliche Kapazitaetsrechnung – keine '95 % Marge / 50k easy'-Maerchen."""
    ticket = max(500.0, float(ticket or 5000))
    target_month = max(ticket, float(target_month or 30000))
    deals_needed = int(round(target_month / ticket))
    # Annahme: Christian braucht ~2–4h Closing+QA pro Deal
    hours_per_deal_christian = 3.0
    weeks = 4.3
    sales_hours_month = hours_week_sales * weeks
    max_deals_by_time = int(sales_hours_month // hours_per_deal_christian) if hours_per_deal_christian else 0

    reality = []
    if deals_needed > max_deals_by_time:
        reality.append(
            {
                "ok": False,
                "check": (
                    f"Ziel {int(target_month)} EUR (~{deals_needed} x {int(ticket)}) "
                    f"braucht mehr Closing-Zeit als {hours_week_sales}h/Woche Sales erlauben "
                    f"(ca. {max_deals_by_time} Deals/Monat bei ~{hours_per_deal_christian}h/Deal)."
                ),
                "action": "Ziel senken, Ticket erhoehen, oder mehr Sales-Stunden einplanen.",
            }
        )
    else:
        reality.append(
            {
                "ok": True,
                "check": (
                    f"Zeitlich grob machbar: ~{deals_needed} Deals/Monat bei "
                    f"{hours_week_sales}h/Woche Closing – wenn Pipeline gefuellt ist."
                ),
            }
        )
    reality.append(
        {
            "ok": False,
            "check": "Fulfillment-Automation ersetzt nicht Trust-Calls und finale QA.",
            "action": "Router/Stefan/Anwalt/Scout bereiten vor – du schliesst.",
        }
    )
    reality.append(
        {
            "ok": False,
            "check": "Keine 95%-Marge-Garantie und kein Helsinki-Standort in Angeboten behaupten.",
            "action": "Echte Kosten: Server, Zeit, optional API-Keys, Steuer, Ruecklagen.",
        }
    )

    markdown = "\n".join(
        [
            "# Solo-Kapazitaet (Orientierung)",
            f"Stand: {date.today().isoformat()}",
            "",
            DISCLAIMER,
            "",
            f"- Ticket: {int(ticket)} EUR",
            f"- Monatsziel (Wunsch): {int(target_month)} EUR -> ca. {deals_needed} Projekte",
            f"- Sales-Stunden/Woche: {hours_week_sales} -> ca. {max_deals_by_time} Closings/Monat machbar",
            f"- Parallele aktive Projekte (Empfehlung Solo): {parallel_active}",
            "",
            "## Reality",
            *[
                f"- {'OK' if r['ok'] else 'ACHTUNG'}: {r['check']}"
                + (f" -> {r['action']}" if r.get("action") else "")
                for r in reality
            ],
            "",
            "## Was nur Christian macht",
            *[f"- {g}" for g in PERSONAL_GATES],
            "",
            "## Was das System vorbereitet",
            "- Scout-Kampagne / Outreach-Entwuerfe",
            "- Stefan-Schlachtplan + Growth",
            "- Anwalt 3-Stufen / DocuSeal-Felder",
            "- Portal/n8n-MVP durch Nils nach Freigabe",
        ]
    )
    return {
        "ok": True,
        "mode": "capacity",
        "ticket": ticket,
        "target_month": target_month,
        "deals_needed": deals_needed,
        "max_deals_by_sales_time": max_deals_by_time,
        "parallel_active_recommended": parallel_active,
        "personal_gates": PERSONAL_GATES,
        "reality": reality,
        "markdown": markdown,
        "disclaimer": DISCLAIMER,
        "auto_send": False,
    }


def fulfillment_pack(
    *,
    firma: str,
    brief: str,
    budget: str = "5000",
    kontakt: str = "",
    zero_retention: bool = True,
) -> dict[str, Any]:
    """Eine Kette: Stefan-Plan + Anwalt-Pipeline + Briefings Texter/Design + Christian-Gates."""
    firma = (firma or "").strip() or "Neuer B2B-Kunde"
    brief = (brief or "").strip() or f"B2B Projekt fuer {firma}, Setup ca. {budget} EUR"
    budget = (budget or "5000").strip()

    plan = stefan.plan_project(brief, firma=firma)
    growth = stefan.growth_plan(brief, ticket=budget)
    pipe = anwalt.pipeline_3_stufen(
        firma=firma,
        kontakt=kontakt,
        leistungen=brief[:300],
        budget=budget,
        zero_retention=zero_retention,
        brief=brief,
    )
    ent = anwalt.enterprise_pack(
        firma=firma,
        kontakt=kontakt,
        leistungen=brief[:300],
        budget=budget,
        zero_retention=zero_retention,
        brief=brief,
    )

    texter_brief = {
        "agent": "texter",
        "workflow": 6,
        "auftrag": (
            f"Landing/Angebotstext fuer {firma}. "
            f"Ton: menschlich (menschlicher-ton). Angebot: {budget} EUR. "
            f"Kein GHL, kein Helsinki, keine Umsatzversprechen."
        ),
        "landing_struktur": growth.get("landingpage"),
        "email_sequenz": growth.get("email_sequence"),
    }
    design_brief = {
        "agent": "design",
        "workflow": 7,
        "auftrag": (
            f"CI-konform Dunkel+Gold fuer {firma}-Material / Portal-Hinweise. "
            "Logo nur freigestelltes Webschmiede-Asset. Kein Generic-AI-Look."
        ),
    }
    lektor_brief = {
        "agent": "lektor",
        "workflow": 8,
        "auftrag": "Texter-Output gegen Floskeln, Gedankenstrich-Overkill und Guru-Claims pruefen.",
    }

    christian = [
        f"Zoom/Telefon mit {firma} – Trust-Abschluss (KI schickt keinen Vertrag blind)",
        "Scope/Preis final bestaetigen",
        "DocuSeal Kundenpaket erst nach deinem OK senden",
        "Anwalt-Ampel lesen: " + str(pipe.get("ampel")),
        "Nach Unterschrift: Nils fuer Portal/n8n freigeben",
        "Finale QA vor Go-Live",
    ]
    nils = plan.get("todos", {}).get("nils") or [
        "Portal-Tenant / n8n-MVP nach Freigabe",
        "Kein neues SaaS ohne OK",
    ]

    # Dauer/Kosten: ehrlich als Spanne, nicht "3 Minuten / 35 Cent"
    ops_meta = {
        "vorbereitungszeit": "System-Pack: Sekunden bis Minuten (API). Menschliche Arbeit: Stunden.",
        "api_kosten": "Optional LLM/Places – nur mit Key und Budget-OK. Deterministische Packs: ~0 EUR API.",
        "nicht_automatisch": PERSONAL_GATES,
    }

    markdown = "\n".join(
        [
            f"# Fulfillment-Pack – {firma}",
            f"Stand: {date.today().isoformat()} | Budget: {budget} EUR",
            "",
            DISCLAIMER,
            "",
            "## Christian (Pflicht – nicht delegierbar)",
            *[f"- {c}" for c in christian],
            "",
            "## Anwalt-Ampel",
            f"- {pipe.get('ampel')} ({len(pipe.get('findings') or [])} Findings)",
            f"- DocuSeal: {ent['docuseal']['url']} · {ent['docuseal']['standard_paket']}",
            "",
            "## Stefan – Minimum-Stack",
            *[f"- {m}" for m in (plan.get("minimum_stack") or [])],
            "",
            "## Briefings an Agenten",
            f"- Texter: {texter_brief['auftrag']}",
            f"- Design: {design_brief['auftrag']}",
            f"- Lektor: {lektor_brief['auftrag']}",
            "",
            "## Nils",
            *[f"- {n}" for n in nils],
            "",
            "## Ops-Meta (ohne Hype)",
            f"- {ops_meta['vorbereitungszeit']}",
            f"- {ops_meta['api_kosten']}",
            "",
            "## Scout (optional naechster Schritt)",
            "- POST /api/agency/scout/campaign – Entwuerfe, Freigabe noetig",
        ]
    )

    return {
        "ok": True,
        "agent": "commander",
        "mode": "fulfillment",
        "firma": firma,
        "budget": budget,
        "disclaimer": DISCLAIMER,
        "hosting": "Hetzner Nuernberg (nicht Helsinki)",
        "stefan": {
            "minimum_stack": plan.get("minimum_stack"),
            "architektur": plan.get("architektur"),
            "onboarding": plan.get("onboarding"),
            "guru_hits": plan.get("guru_hits"),
        },
        "growth": {
            "landingpage": growth.get("landingpage"),
            "email_sequence": growth.get("email_sequence"),
            "verkaufs_schnitt": growth.get("verkaufs_schnitt"),
        },
        "anwalt": {
            "ampel": pipe.get("ampel"),
            "findings": pipe.get("findings"),
            "docuseal_fields": ent.get("docuseal_fields"),
            "document_preview": (pipe.get("document") or "")[:2000],
        },
        "briefings": {
            "texter": texter_brief,
            "design": design_brief,
            "lektor": lektor_brief,
        },
        "todos": {"christian": christian, "nils": nils},
        "ops_meta": ops_meta,
        "personal_gates": PERSONAL_GATES,
        "markdown": markdown,
        "auto_send": False,
        "rechtskraft": False,
    }


def daily_briefing(*, scout_limit: int = 5, ticket: str = "5000") -> dict[str, Any]:
    """Tageslage fuer den Commander: Queue, Freigaben, persoenliche To-dos."""
    q = scout.queue_summary(limit=40)
    camp = scout.campaign(limit=scout_limit, ticket=ticket)
    pending = akquise.list_items(status="approve")[:10]
    later = akquise.due_reminders()[:10]

    christian_today = [
        "Trust-Calls / Abschluesse (nicht an KI abgeben)",
        "Outreach-Entwuerfe pruefen und freigeben oder verwerfen",
        "DocuSeal nur bewusst senden",
    ]
    if camp.get("count"):
        christian_today.insert(
            0,
            f"{camp['count']} Scout-Entwuerfe bereit – max. 5 personalisierte Kontakte heute",
        )
    if later:
        christian_today.append(f"{len(later)} Akquise-Rueckrufe faellig")

    markdown = "\n".join(
        [
            f"# Commander Tagesbriefing – {date.today().isoformat()}",
            "",
            DISCLAIMER,
            "",
            f"## Pipeline",
            f"- Buy-Queue gesamt (Sample): {q.get('count')}",
            f"- Nach Vertical: {q.get('by_vertical')}",
            f"- Kampagne Top-Entwuerfe: {camp.get('count')}",
            f"- Approvals (approve): {len(pending)} | Reminder: {len(later)}",
            "",
            "## Nur du",
            *[f"- {c}" for c in christian_today],
            "",
            "## Top-Leads (Entwurf, kein Versand)",
        ]
    )
    for i, lead in enumerate(camp.get("leads") or [], 1):
        markdown += (
            f"\n{i}. **{lead.get('name')}** ({lead.get('vertical')}) "
            f"Score {lead.get('score')} – {lead.get('phone') or 'kein Tel'}"
        )
    if not camp.get("leads"):
        markdown += "\n- Keine buy-ready Leads. Frischen Akquise-Lauf nur mit Kosten-OK."

    return {
        "ok": True,
        "agent": "commander",
        "mode": "daily_briefing",
        "date": date.today().isoformat(),
        "disclaimer": DISCLAIMER,
        "queue": q,
        "campaign_preview": {
            "count": camp.get("count"),
            "leads": [
                {
                    "name": L.get("name"),
                    "vertical": L.get("vertical"),
                    "score": L.get("score"),
                    "phone": L.get("phone"),
                    "subject": (L.get("outreach") or {}).get("subject"),
                }
                for L in (camp.get("leads") or [])
            ],
        },
        "approvals_approve": pending,
        "reminders_due": later,
        "todos_christian": christian_today,
        "personal_gates": PERSONAL_GATES,
        "markdown": markdown,
        "auto_send": False,
        "next_commands": [
            "python scripts/scout_campaign_cli.py --limit 5",
            "python scripts/commander_cli.py --fulfillment --firma \"…\" --budget 5000 \"…\"",
            "python scripts/commander_cli.py --capacity --ticket 5000 --target 30000",
        ],
    }
