"""Stefan – CEO, Guru-Filter, B2B-Schlachtplan (Workflow #2)."""
from __future__ import annotations

import re
from typing import Any

SYSTEM_PROMPT = """Du bist Stefan, der unbestechliche, hyper-rationale CEO und Chef-Stratege der Webschmiede.
Dein Gruender Christian neigt dazu, sich von YouTube-Trends (GoHighLevel, SMS-Bots, WhatsApp-Automationen,
Speedscaling, Infopreneur-Millionenumsatz) inspirieren zu lassen. Deine primaere Aufgabe: ihn auf den Boden holen.

Eiserne Regeln:
1. RADIKALE SIMPLIZITAET: Niemals neues Drittanbieter-Tool oder teure API, wenn n8n + eigene DB/Portal + E-Mail reichen.
2. B2B-STANDARD: Deutsche B2B-Kunden (Handwerk, Grosshandel, Industrie) wollen Stabilitaet und DSGVO, keine Spielereien.
3. ERGEBNIS-ORIENTIERUNG: Christian braucht einen klaren Schlachtplan fuer Nils, keinen Tool-Salat.
4. WACHSTUM OHNE SPAM: Landingpage + E-Mail-Sequenz + Onboarding nur als Entwuerfe. Kein Auto-Send ohne Freigabe.

Antwort-Struktur:
- Reality-Check (Guru-Brainwash oder sinnvoll? Warum?)
- Das absolute Minimum (2-3 Core-Systeme)
- Bauplan fuer Nils
- Fahrplan fuer Christian

Stack-Wahrheit Webschmiede: eigenes Portal (Flask), eigenes CRM, n8n, Hetzner DE Nuernberg, DocuSeal, Lexware-Pfad.
Kein GHL. WhatsApp/SMS nur wenn wirklich noetig und freigegeben. Kein Budibase-Zwang.
Keine Kunden-Mails oder Kaeufe ohne Christians OK.
"""

STACK_TRUTH = """
Webschmiede-Wahrheit (nicht Guru-Stack):
- Eigenes Dashboard/Portal (Cursor/Flask), kein Budibase/Softr-Zwang
- B2B-Gesicht fuer n8n: /b2b-portal.html + /api/b2b/jobs (Upload, Berechnung, Tabelle)
- CRM eigen (contacts), kein GHL
- Automation: n8n auf Agentur-Server
- Buchhaltung: Lexware-Pfad / E-Mail-Belege
- Vertraege: DocuSeal
- Hosting: Hetzner DE (Nuernberg), EU
- B2B-Kommunikation: zuerst E-Mail + Portal, nicht Meta-Pflicht
- Keine Kunden-Mails/Rechnungen ohne Freigabe
"""

# pattern -> (urteil, warum, alternative)
GURU_PATTERNS: list[tuple[tuple[str, ...], str, str, str]] = [
    (
        ("gohighlevel", "ghl", "highlevel"),
        "ablehnen",
        "All-in-One-CRM mit Affiliate-Druck. Teuer, US-lastig, unnoetig.",
        "Eigenes CRM (contacts) + n8n + DocuSeal + E-Mail.",
    ),
    (
        ("manychat", "chatbot funnel", "many chat"),
        "ablehnen",
        "Chat-Funnel fuer Massengeschaeft, nicht High-Ticket-B2B.",
        "E-Mail + eigenes Portal / Onboarding-Link.",
    ),
    (
        ("sms marketing", "sms-marketing", "sms spam", "sms blast", "sms kampagne", "sms-kampagne"),
        "ablehnen",
        "Im DE-B2B schnell unserioes und abmahnrelevant.",
        "E-Mail (SMTP) oder persoenlicher Anruf durch Christian.",
    ),
    (
        ("whatsapp bot", "whatsapp-bot", "whatsapp fuer alles", "whatsapp für alles", "wa bot", "whatsapp automation"),
        "vorsicht",
        "Offiziell ok, aber DSGVO/Meta-Overhead und Kosten pro Nachricht. Fuer High-Ticket oft zu unruhig.",
        "E-Mail + Portal. WhatsApp nur fuer klaren Support-Kanal mit Meta-Keys und AVV.",
    ),
    (
        ("twilio", "sms gateway ueberall"),
        "vorsicht",
        "Sinnvoll nur fuer konkrete Voice/SMS-Faelle mit Budget-OK, kein Default.",
        "E-Mail zuerst. Twilio/Retell nur wenn Voice wirklich verkauft wird.",
    ),
    (
        ("airtable abo", "notion crm", "hubspot"),
        "vorsicht",
        "Neue SaaS-Schicht, die wir oft nicht brauchen.",
        "SQLite/Postgres auf Hetzner + eigenes Dashboard.",
    ),
    (
        ("budibase", "softr"),
        "vorsicht",
        "Moeglich, aber bei euch schon eigenes Portal-Stack. Kein Pflicht-Tool.",
        "Bestehendes Flask/Kundenportal erweitern.",
    ),
    (
        ("speedscaling", "millionenumsatz", "millionen umsatz", "infopreneur", "high ticket guru"),
        "vorsicht",
        "Marketing-Hype. Architektur hilft, Garantien und Spam-Funnels nicht.",
        "Eigene Portale + Scout mit Freigabe + DocuSeal. Kein Auto-Spam.",
    ),
    (
        ("kaltakquise spam", "vollautomatisch kunden", "auto outreach ohne freigabe", "1000 mails am tag"),
        "ablehnen",
        "Rechtlich und reputationsseitig gefaehrlich. Webschmiede sendet nur mit Freigabe.",
        "Scout-Queue + Outreach-Entwurf + Christian genehmigt.",
    ),
    (
        ("95% marge", "95 % marge", "marge von 95", "30.000 € garantiert", "50000 euro easy", "one man army 100k"),
        "ablehnen",
        "Umsatz-/Marge-Garantien aus Guru-Content. Nicht planbar, nicht versprechen.",
        "Capacity-Plan ehrlich: Closing-Zeit + Pipeline. Commander-Pack ohne Garantie.",
    ),
    (
        ("server in helsinki", "hetzner helsinki", "rechenzentrum helsinki", "finnland hosting live"),
        "ablehnen",
        "Live-Hosting ist Nuernberg, nicht Helsinki.",
        "Immer Hetzner Deutschland (Nuernberg) kommunizieren.",
    ),
]


def _norm(s: str) -> str:
    s = (s or "").lower()
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return s


def scan_guru(text: str) -> list[dict[str, str]]:
    t = _norm(text)
    hits: list[dict[str, str]] = []
    for keys, urteil, warum, alt in GURU_PATTERNS:
        if any(k in t for k in keys):
            hits.append(
                {
                    "match": next(k for k in keys if k in t),
                    "urteil": urteil,
                    "warum": warum,
                    "alternative": alt,
                }
            )
    return hits


def _detect_modules(brief: str) -> list[str]:
    t = _norm(brief)
    mods: list[str] = []
    if any(x in t for x in ("buchhalt", "rechnung", "lexware", "beleg", "ocr", "datev")):
        mods.append("buchhaltung")
    if any(
        x in t
        for x in ("haendler", "handler", "wholesale", "keepa", "marge", "ean", "amazon", "kalkul", "listen")
    ):
        mods.append("wholesale")
    if any(x in t for x in ("dashboard", "portal", "upload", "cockpit")):
        mods.append("dashboard")
    if any(x in t for x in ("whatsapp", "sms", "messaging")):
        mods.append("messaging")
    if any(x in t for x in ("voice", "anruf", "retell")):
        mods.append("voice")
    if any(x in t for x in ("website", "landing", "shop")):
        mods.append("website")
    if not mods:
        mods.append("custom")
    if ("wholesale" in mods or "buchhaltung" in mods) and "dashboard" not in mods:
        mods.append("dashboard")
    return mods


def _budget(brief: str) -> str | None:
    m = re.search(r"(\d+)\s*k\b", brief, re.I)
    if m:
        return f"{m.group(1)}.000 EUR (geschaetzt)"
    m = re.search(r"(\d{1,3}(?:[.,]\d{3})*|\d+)\s*(?:€|euro|eur)\b", brief, re.I)
    if m:
        return m.group(0).replace(",", ".")
    return None


def _minimum_stack(modules: list[str], guru_hits: list[dict[str, str]]) -> list[str]:
    base = [
        "E-Mail SMTP/IMAP (Onboarding, Vertraege, Reports)",
        "Eigenes Kunden-Portal auf Hetzner (Upload/Status)",
        "n8n auf Agentur-Server (Automationen)",
    ]
    if "buchhaltung" in modules:
        base.append("Lexware-Pfad oder Beleg-Export (kein neues Buchhaltungs-SaaS)")
    if "wholesale" in modules:
        base.append("CSV-Pipeline in n8n; Keepa erst nach Kosten-OK")
    if any(h["urteil"] == "ablehnen" for h in guru_hits):
        base.append("Ausdruecklich OHNE GHL / SMS-Marketing / Chat-Funnel-SaaS")
    # unique preserve order
    seen: set[str] = set()
    out: list[str] = []
    for b in base:
        if b not in seen:
            seen.add(b)
            out.append(b)
    return out[:5]


def filter_idea(idea: str) -> dict[str, Any]:
    """Guru-Filter fuer Tool-Ideen und Trends. Keine Side-Effects."""
    text = (idea or "").strip()
    if not text:
        return {"ok": False, "error": "idea fehlt"}

    hits = scan_guru(text)
    if not hits:
        verdict = "pruefen"
        summary = (
            "Kein klassischer Guru-Trigger erkannt. Trotzdem: reicht E-Mail + Portal + n8n? "
            "Neues Tool nur mit klarem Mehrwert und Budget-OK."
        )
    elif any(h["urteil"] == "ablehnen" for h in hits):
        verdict = "ablehnen"
        summary = "Guru-/Affiliate-Muster erkannt. Fuer High-Ticket-B2B ablehnen oder stark einschraenken."
    else:
        verdict = "vorsicht"
        summary = "Kann Sinn machen, ist aber nicht Default. Erst Minimum-Stack, dann optional."

    minimum = _minimum_stack(_detect_modules(text), hits)
    bauplan_nils = [
        "Kein neues Abo installieren ohne Christians OK",
        "Bestehende n8n-Workflows und Portal-Pfade wiederverwenden",
        "Secrets nur in Server-.env / deploy.secrets.local",
    ]
    if verdict == "ablehnen":
        bauplan_nils.insert(0, "Vorschlag ablehnen; Alternative aus Minimum-Stack umsetzen")
    fahrplan = [
        "Idee gegen Reality-Check halten (dieses Dokument)",
        "Kunde/Use-Case in einem Satz: Problem + Ergebnis",
        "Wenn ja: Nils nur Minimum-Stack bauen lassen",
        "Keine Meta/SMS/GHL-Kaue ohne ausdrueckliches OK",
    ]

    markdown = _filter_markdown(text, verdict, summary, hits, minimum, bauplan_nils, fahrplan)
    return {
        "ok": True,
        "agent": "stefan",
        "mode": "guru_filter",
        "workflow": 2,
        "verdict": verdict,
        "summary": summary,
        "guru_hits": hits,
        "minimum_stack": minimum,
        "bauplan_nils": bauplan_nils,
        "fahrplan_christian": fahrplan,
        "markdown": markdown,
        "system_prompt": SYSTEM_PROMPT.strip(),
        "auto_send": False,
    }


def plan_project(brief: str, *, firma: str = "") -> dict[str, Any]:
    """Schlachtplan aus Rohwunsch inkl. Guru-Filter. Keine Side-Effects."""
    text = (brief or "").strip()
    if not text:
        return {"ok": False, "error": "brief fehlt"}

    guru_hits = scan_guru(text)
    modules = _detect_modules(text)
    budget = _budget(text)
    firma = (firma or "").strip() or "Neuer B2B-Kunde"
    minimum = _minimum_stack(modules, guru_hits)

    # Messaging-Modul abschwaechen wenn Guru-WhatsApp/SMS
    if "messaging" in modules and any(
        h["match"] for h in guru_hits if "sms" in h["match"] or "whatsapp" in h["match"]
    ):
        pass  # bleibt, aber Reality warnt

    architektur: list[dict[str, str]] = []
    if "wholesale" in modules:
        architektur.append(
            {
                "modul": "Haendlerlisten / Wholesale-Kalkulation",
                "bauen": (
                    "n8n: CSV/Excel-Upload -> EAN normalisieren -> optionale Preis-API "
                    "(Keepa nur mit Key+OK) -> Gebuehren/Marge -> Ergebnis ins eigene Kunden-Portal."
                ),
                "wer": "Nils + Christian (Formeln/Freigabe)",
                "risiko": "API-Kosten; falsche Margen ohne klare Regeln",
            }
        )
    if "buchhaltung" in modules:
        architektur.append(
            {
                "modul": "Vorbereitende Buchhaltung",
                "bauen": (
                    "n8n: Belege aus Postfach oder Upload -> Metadaten/OCR wo noetig -> "
                    "Lexware-Schnittstelle oder CSV fuer Steuerberater."
                ),
                "wer": "Nils + Finanz-Workflow",
                "risiko": "Keine Steuerberatung; Kunde bleibt verantwortlich",
            }
        )
    if "dashboard" in modules:
        architektur.append(
            {
                "modul": "Kunden-Dashboard",
                "bauen": (
                    "Eigenes Portal auf Hetzner (Flask): Login, Upload, Status, Ergebnis-Tabellen. "
                    "Kein GHL, kein Pflicht-Budibase."
                ),
                "wer": "Nils + Christian",
                "risiko": "Scope-Creep; MVP festnageln",
            }
        )
    if "messaging" in modules:
        architektur.append(
            {
                "modul": "Messaging (optional)",
                "bauen": (
                    "Default: E-Mail. WhatsApp Cloud API / SMS nur nach Meta-Keys, AVV und klarem Use-Case. "
                    "Kein SMS-Marketing."
                ),
                "wer": "Nils nach Freigabe",
                "risiko": "Meta-Sperren, DSGVO, Kosten",
            }
        )
    if "custom" in modules and len(modules) == 1:
        architektur.append(
            {
                "modul": "Individuell",
                "bauen": "In 1-3 n8n/Portal-Bausteine zerlegen, MVP in 2 Wochen.",
                "wer": "Stefan plant, Nils baut",
                "risiko": "Unklarer Scope",
            }
        )

    onboarding = {
        "schritte": [
            "Preis/Leistung muendlich bestaetigen",
            "DocuSeal Kundenpaket senden (kein Blind-Auto)",
            "Onboarding im eigenen System: Firmendaten, Module, Ansprechpartner",
            "Zugänge erst nach Unterschrift + Zahlung/Freigabe",
            "Nils: Portal + n8n-MVP",
        ],
        "mail_entwurf": _onboarding_mail_draft(firma, budget),
        "hinweis": "Mail/Rechnung nur nach OK von Christian.",
        "workflows_danach": ["finanz", "texter", "lektor"],
    }

    todos_christian = [
        "Scope und Preis mit Kunde final machen",
        "DocuSeal-Paket senden",
        "Keine GHL/SMS/WhatsApp-Pflicht verkaufen, wenn E-Mail+Portal reicht",
        "Nils freigeben fuer MVP",
    ]
    todos_nils = [
        "Portal-Tenant vorbereiten",
        "n8n-Skelette pro Modul (inactive bis Keys)",
        "Kein neues SaaS ohne OK",
    ]

    reality_lines = _reality_narrative(text, guru_hits, modules)
    markdown = _plan_markdown(
        firma=firma,
        budget=budget,
        brief=text,
        modules=modules,
        guru_hits=guru_hits,
        reality_lines=reality_lines,
        minimum=minimum,
        architektur=architektur,
        onboarding=onboarding,
        todos_christian=todos_christian,
        todos_nils=todos_nils,
    )

    return {
        "ok": True,
        "agent": "stefan",
        "mode": "schlachtplan",
        "workflow": 2,
        "firma": firma,
        "budget": budget,
        "modules": modules,
        "guru_hits": guru_hits,
        "reality_check": reality_lines,
        "minimum_stack": minimum,
        "architektur": architektur,
        "onboarding": onboarding,
        "todos": {"christian": todos_christian, "nils": todos_nils},
        "bauplan_nils": [f"{a['modul']}: {a['bauen']}" for a in architektur] + todos_nils,
        "fahrplan_christian": todos_christian,
        "next_agents": ["finanz", "texter", "lektor", "nils"],
        "markdown": markdown,
        "system_prompt": SYSTEM_PROMPT.strip(),
        "stack_truth": STACK_TRUTH.strip(),
        "auto_send": False,
    }


def _reality_narrative(text: str, hits: list[dict[str, str]], modules: list[str]) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    if hits:
        for h in hits:
            lines.append(
                {
                    "ok": h["urteil"] != "ablehnen",
                    "check": f"{h['match']}: {h['warum']}",
                    "action": h["alternative"],
                    "urteil": h["urteil"],
                }
            )
    else:
        lines.append(
            {
                "ok": True,
                "check": "Kein GHL/SMS-Spam/Chat-Funnel-Trigger. Idee kann geprueft werden.",
                "urteil": "pruefen",
            }
        )
    lines.append(
        {
            "ok": True,
            "check": "High-Ticket-B2B (ca. 5-10k): Stabilitaet und E-Mail/Portal schlagen Tool-Zoo.",
            "urteil": "ok",
        }
    )
    if "messaging" in modules:
        lines.append(
            {
                "ok": False,
                "check": "Messaging genannt: nicht als Pflicht verkaufen.",
                "action": "E-Mail + Portal zuerst; WhatsApp/SMS nur mit klarem Nutzen und OK",
                "urteil": "vorsicht",
            }
        )
    if "wholesale" in modules:
        lines.append(
            {
                "ok": False,
                "check": "Keepa/Amazon-API kostet Geld.",
                "action": "Erst CSV-Rechner, API nur nach OK",
                "urteil": "vorsicht",
            }
        )
    for r in (
        "Kein neues SaaS, wenn n8n + Portal + E-Mail reichen.",
        "Keine Auto-Mails/Rechnungen ohne Freigabe.",
    ):
        lines.append({"ok": True, "check": r, "urteil": "ok"})
    return lines


def _onboarding_mail_draft(firma: str, budget: str | None) -> str:
    preis = budget or "[Betrag]"
    return (
        f"Betreff: Naechste Schritte - {firma}\n\n"
        f"Guten Tag,\n\n"
        f"danke fuer das Vertrauen. Wir setzen das Projekt wie besprochen um ({preis}).\n\n"
        f"Als Naechstes schicken wir Ihnen den Auftrag inkl. AGB und AVV zum Unterschreiben. "
        f"Danach brauchen wir die Zugaenge/Dateien fuer den Start "
        f"(z. B. Beispiel-Haendlerliste oder Postfach fuer Belege).\n\n"
        f"Bei Fragen einfach kurz melden.\n\n"
        f"Viele Gruesse\nChristian Kummetat\nWebschmiede / Digitale Handwerkskunst\n"
    )


def _filter_markdown(
    idea: str,
    verdict: str,
    summary: str,
    hits: list[dict[str, str]],
    minimum: list[str],
    bauplan_nils: list[str],
    fahrplan: list[str],
) -> str:
    lines = [
        "# Stefan - Guru-Filter / Reality-Check",
        "",
        f"**Urteil:** {verdict}",
        f"**Kurz:** {summary}",
        "",
        "## 1) Reality-Check",
    ]
    if hits:
        for h in hits:
            lines.append(f"- [{h['urteil']}] {h['match']}: {h['warum']}")
            lines.append(f"  Alternative: {h['alternative']}")
    else:
        lines.append("- Kein harter Guru-Treffer. Trotzdem Minimum-Stack bevorzugen.")
    lines += ["", "## 2) Das absolute Minimum", *[f"- {m}" for m in minimum]]
    lines += ["", "## 3) Bauplan fuer Nils", *[f"- {b}" for b in bauplan_nils]]
    lines += ["", "## 4) Fahrplan fuer Christian", *[f"- {f}" for f in fahrplan]]
    lines += ["", "## Idee", idea[:800], "", SYSTEM_PROMPT.strip()]
    return "\n".join(lines)


def _plan_markdown(
    *,
    firma: str,
    budget: str | None,
    brief: str,
    modules: list[str],
    guru_hits: list[dict[str, str]],
    reality_lines: list[dict[str, Any]],
    minimum: list[str],
    architektur: list[dict[str, str]],
    onboarding: dict[str, Any],
    todos_christian: list[str],
    todos_nils: list[str],
) -> str:
    lines = [
        f"# Stefan - Schlachtplan: {firma}",
        "",
        f"**Budget:** {budget or 'nicht genannt'}",
        f"**Module:** {', '.join(modules)}",
        "",
        "## 1) Reality-Check",
    ]
    for r in reality_lines:
        mark = r.get("urteil") or ("OK" if r.get("ok") else "ACHTUNG")
        lines.append(f"- [{mark}] {r['check']}" + (f" -> {r['action']}" if r.get("action") else ""))
    if guru_hits:
        lines.append("- Guru-Treffer siehe oben; nicht den Tool-Zoo verkaufen.")
    lines += ["", "## 2) Das absolute Minimum", *[f"- {m}" for m in minimum]]
    lines += ["", "## 3) Bauplan fuer Nils"]
    for a in architektur:
        lines += [f"### {a['modul']}", f"- {a['bauen']}", f"- Wer: {a['wer']}", f"- Risiko: {a['risiko']}", ""]
    lines += [*[f"- Todo: {t}" for t in todos_nils]]
    lines += [
        "",
        "## 4) Fahrplan fuer Christian",
        *[f"- {t}" for t in todos_christian],
        "",
        "### Onboarding (kein Auto-Versand)",
        *[f"- {s}" for s in onboarding["schritte"]],
        "",
        "### Mail-Entwurf",
        "```",
        onboarding["mail_entwurf"].rstrip(),
        "```",
        "",
        "## Rohwunsch",
        brief[:800],
        "",
        STACK_TRUTH.strip(),
    ]
    return "\n".join(lines)


def growth_plan(
    brief: str = "",
    *,
    niche: str = "",
    ticket: str = "5000",
    offer: str = "",
) -> dict[str, Any]:
    """Wachstums-/Funnel-Stratege: Landing, E-Mail-Sequenz, Verkaufs-Schnitt. Kein Auto-Send."""
    text = (brief or "").strip() or "B2B High-Ticket Portal + Automation"
    niche = (niche or "").strip() or _guess_niche(text)
    ticket = (ticket or _budget(text) or "5000").strip()
    offer = (offer or "").strip() or (
        f"Eigenes gebrandetes B2B-Portal + n8n-Automation auf Hetzner DE "
        f"(Setup ca. {ticket} EUR netto, je nach Scope)"
    )
    hits = scan_guru(text + " " + offer)

    landing = {
        "ziel": f"Ein Termin / Klarheit fuer {niche}-Entscheider, nicht Massenklick",
        "struktur": [
            {
                "block": "Hero",
                "inhalt": (
                    f"Marke Webschmiede dominant. Eine Headline zum Problem von {niche}. "
                    "Ein Satz Nutzen. Ein CTA: Termin / Anfrage. Kein Stat-Strip, keine Pill-Cluster."
                ),
            },
            {
                "block": "Problem",
                "inhalt": "Alltag ohne Portal: Excel, Lieferantenlisten, manuelle Buchhaltung, Tool-Zoo.",
            },
            {
                "block": "Loesung",
                "inhalt": "Eigenes Dashboard auf euren EU-Servern + n8n im Hintergrund. Kein GHL-Brei.",
            },
            {
                "block": "Beweis",
                "inhalt": "Stack-Wahrheit: Hetzner Nuernberg, DocuSeal, AVV, Zero-Retention Option. Kurz, konkret.",
            },
            {
                "block": "Ablauf",
                "inhalt": "Gespraech -> Angebot/DocuSeal -> Onboarding-Link -> Portal live.",
            },
            {
                "block": "CTA",
                "inhalt": "Eine Aktion: Anfrage oder Cal-Link. Kein WhatsApp-Pflicht.",
            },
        ],
        "verboten": [
            "Zehn CTAs",
            "Fake-Testimonials",
            "GHL/Softr als Produkt verkaufen",
            "Helsinki als Standort",
        ],
        "naechster_agent": "texter (+ design fuer CI)",
    }

    sequenz = [
        {
            "nr": 1,
            "tag": 0,
            "zweck": "Wert + Relevanz",
            "betreff": f"Frage zu {niche} / Listen und Portal",
            "koerper_skizze": (
                "Kurzer Bezug zum konkreten Alltag (Listen, Margen, Belege). "
                "Ein Satz was wir gebaut haben (eigenes Portal, kein Fremd-SaaS). "
                "Frage: Passt ein kurzes Gespraech?"
            ),
        },
        {
            "nr": 2,
            "tag": 3,
            "zweck": "Konkretisierung",
            "betreff": "Kurz: so laeuft das bei uns",
            "koerper_skizze": (
                "3 Schritte: Upload/Prozess -> Auswertung im Dashboard -> Onboarding. "
                "Hinweis DSGVO/EU-Server. Kein Druck."
            ),
        },
        {
            "nr": 3,
            "tag": 7,
            "zweck": "Soft close",
            "betreff": "Noch offen?",
            "koerper_skizze": (
                "Ein Satz. Entweder Termin oder sauberer Abschluss. "
                "Kein dritter Follow-up ohne neues Signal."
            ),
        },
    ]

    verkaufs_schnitt = {
        "schritte": [
            "Scout liefert Leads (WF3) – Christian priorisiert",
            "Outreach-Entwurf nur nach Freigabe senden (kein Auto-Spam)",
            "Gespraech: Problem, Scope, Preisrahmen",
            "Stefan-Schlachtplan + Anwalt-Pipeline / DocuSeal Kundenpaket",
            "Zahlung/Freigabe -> Onboarding-Link (eigenes System)",
            "Nils: Portal + n8n-MVP",
        ],
        "automatisiert_ohne_zutun": False,
        "hinweis": (
            "Vollautomatisches Onboarding ohne Christian ist Absicht erst spaeter. "
            "Heute: DocuSeal + Onboarding-UI, Freigabe bleibt menschlich."
        ),
    }

    todos_christian = [
        "Eine Nische/Landing festlegen (nicht zehn)",
        "Scout-Lauf fuer diese Nische anstossen / Queue lesen",
        "Erste 5 Outreach-Entwuerfe freigeben oder verwerfen",
        "Termin-Link/Anfrage-Ziel klar machen",
    ]
    todos_nils = [
        "Landing nur wenn gewuenscht auf bestehendem Stack (agency-web / Static)",
        "Scout-API / Akquise-Report aktuell halten",
        "Kein neues Funnel-SaaS",
    ]

    markdown = "\n".join(
        [
            f"# Stefan Growth – {niche}",
            f"Ticket-Orientierung: {ticket} EUR",
            f"Angebot: {offer}",
            "",
            "## Disclaimer",
            "Strategie-Entwurf. Kein Auto-Send. Keine Umsatzgarantie.",
            "",
            "## Reality-Check",
            *(
                [f"- {h['match']}: {h['urteil']} – {h['warum']}" for h in hits]
                if hits
                else ["- Kein Spam/GHL-Trigger. Wachstum ueber eigenes System + Freigabe."]
            ),
            "",
            "## Landingpage-Struktur (fuer Texter)",
            *[f"- **{b['block']}:** {b['inhalt']}" for b in landing["struktur"]],
            "",
            "### Verboten",
            *[f"- {v}" for v in landing["verboten"]],
            "",
            "## E-Mail-Sequenz (Entwurf, Freigabe noetig)",
            *[
                f"### Mail {m['nr']} (Tag {m['tag']}) – {m['zweck']}\n"
                f"Betreff: {m['betreff']}\n{m['koerper_skizze']}"
                for m in sequenz
            ],
            "",
            "## Verkaufs-Schnitt / Onboarding",
            *[f"- {s}" for s in verkaufs_schnitt["schritte"]],
            f"- Automatisiert ohne Christian: {verkaufs_schnitt['automatisiert_ohne_zutun']}",
            f"- {verkaufs_schnitt['hinweis']}",
            "",
            "## Todos Christian",
            *[f"- {t}" for t in todos_christian],
            "",
            "## Todos Nils",
            *[f"- {t}" for t in todos_nils],
            "",
            "## Naechster Workflow",
            "- Scout/Outreach: POST /api/agency/scout/campaign",
            "",
            STACK_TRUTH.strip(),
        ]
    )

    return {
        "ok": True,
        "agent": "stefan",
        "mode": "growth",
        "workflow": 2,
        "niche": niche,
        "ticket": ticket,
        "offer": offer,
        "guru_hits": hits,
        "landingpage": landing,
        "email_sequence": sequenz,
        "verkaufs_schnitt": verkaufs_schnitt,
        "todos": {"christian": todos_christian, "nils": todos_nils},
        "next_agents": ["scout", "outreach", "texter", "lektor"],
        "markdown": markdown,
        "system_prompt": SYSTEM_PROMPT.strip(),
        "auto_send": False,
    }


def _guess_niche(text: str) -> str:
    t = _norm(text)
    for key, label in (
        ("gastro", "Gastro"),
        ("handwerk", "Handwerk"),
        ("wholesale", "Wholesale / Haendler"),
        ("haendler", "Wholesale / Haendler"),
        ("keepa", "Wholesale / Amazon"),
        ("dach", "Dach"),
        ("dental", "Dental"),
        ("friseur", "Friseur"),
    ):
        if key in t:
            return label
    return "B2B / lokale Betriebe"
