# -*- coding: utf-8 -*-
"""Mandatory 10-stage execution pipeline — no silent skips."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from nils_job_runtime import capability_preflight as pref
from nils_job_runtime import store
from nils_job_runtime import turn_context as tc
from nils_job_runtime import turn_routing as tr
from nils_job_runtime.model import PIPELINE_STAGES

log = logging.getLogger("nils_job_runtime.pipeline")

# Intent → capability mapping (conservative; unknown → clarify)
_INTENT_CAPABILITY = (
    # Street-UX: Liste lesen — Plural „Termine …“, nicht Singular „Termin morgen“ (Create/Close)
    (
        re.compile(
            r"(?i)\b("
            r"termine\s+(?:heute|morgen)|"
            r"termine\s+zeigen|"
            r"termin\s+heute\b|"
            r"kalender\s*(?:lesen|prüfen|pruefen)|"
            r"was\s+steht\s+heute|"
            r"was\s+steht\s+(?:heute\s+)?im\s+kalender"
            r")\b"
        ),
        "calendar.read",
        "read",
    ),
    (re.compile(r"(?i)\b(freie\s+zeit|freebusy|verfügbarkeit|verfuegbarkeit)\b"), "calendar.freebusy", "read"),
    (re.compile(r"(?i)\b(termin\s+vorbereiten|kalender\s+vorbereiten)\b"), "calendar.prepare", "prepare"),
    # Zug H: Street-Close-Kombi vor generischem termin→create
    (
        re.compile(
            r"(?i)\b("
            r"feld[- ]?close|"
            r"street[- ]?close|"
            r"nach\s+dem\s+(?:gespräch|gespraech)|"
            r"(?:notiz|notiere|vermerke)\s*[:=]|"
            r"speicher\w*\s+(?:eine?\s+)?notiz"
            r")\b"
        ),
        "crm.note_create",
        "write",
    ),
    (re.compile(r"(?i)\b(termin\s+(anlegen|erstellen)|kalender\s+eintragen)\b"), "calendar.create", "write"),
    (re.compile(r"(?i)\b(termin\s+(ändern|aendern|update))\b"), "calendar.update", "write"),
    (re.compile(r"(?i)\b(termin\s+(löschen|loeschen|delete))\b"), "calendar.delete", "write"),
    (re.compile(r"(?i)\b(teilnehmer\s+einladen|einladung\s+senden)\b"), "calendar.invite", "write"),
    (re.compile(r"(?i)\b(termin|meeting|eintragen)\b"), "calendar.create", "write"),
    (re.compile(r"(?i)\bkalender\b"), "calendar.read", "read"),
    # SM-3: Angebot PDF an Allowlist-Empfänger (before generic email / offer pdf telegram)
    (
        re.compile(
            r"(?i)("
            r"\bangebot\s+pdf\s+an\b|"
            r"(?:schick|sende|send)\w*\s+(?:das\s+|ein\s+)?angebot\w*\s+"
            r"(?:von\s+.+?\s+)?an\s+[\w.+-]+@[\w.-]+\.\w+|"
            r"(?:schick|sende)\w*\s+angebot\w*\s+pdf\s+an\b|"
            r"\bpdf\s+angebot\s+an\s+[\w.+-]+@"
            r")"
        ),
        "crm.email_send",
        "send",
    ),
    # CRM agency e-mail (allowlist + Freigabe) — before generic email.send
    (
        re.compile(
            r"(?i)\b("
            r"(?:schreib|schreibe|sende|schick)\w*\s+(?:eine?\s+|mir\s+eine?\s+)?(?:e-?mail|mail)\s+an|"
            r"(?:e-?mail|mail)\s+an\s+\S+|"
            r"(?:e-?mail|mail)\s+(?:schreiben|senden|schicken)\s+an|"
            r"crm[- ]?mail|"
            r"agency[- ]?mail"
            r")\b"
        ),
        "crm.email_send",
        "send",
    ),
    (re.compile(r"(?i)\b(mail\s*senden|e-?mail\s*senden|versenden)\b"), "email.send", "send"),
    (re.compile(r"(?i)\b(ggg\s*postings?\s*(finden|suchen)|postings?\s*finden)\b"), "ggg.postings_find", "read"),
    (re.compile(r"(?i)\b(posting\s*prüfen|posting\s*pruefen|beitrag\s*prüfen|ggg\s*prüfen)\b"), "posting.check", "check"),
    (re.compile(r"(?i)\b(veröffentlichen|veroeffentlichen|posten|publish)\b"), "posting.publish", "publish"),
    (re.compile(r"(?i)\b(n8n|workflow\s*starten)\b"), "n8n.execute", "execute"),
    (
        re.compile(
            r"(?i)^\s*shadowjob\s+(?:echo|steps|fail|block|heartbeat_long)\b"
        ),
        "shadow.echo",
        "prepare",
    ),
    # Prospect create (Interessent / potentieller Kunde) — before blocked customer_write
    (
        re.compile(
            r"(?i)(?:"
            r"\b(?:interessent(?:en)?|prospect|potentiell\w*\s+kunden?)\s+(?:anlegen|erstellen)\b|"
            r"\b(?:anlegen|erstellen)\s+(?:eines?\s+|einen?\s+)?"
            r"(?:interessenten?|prospect|potentiell\w*\s+kunden?)\b|"
            r"\blege?\s+(?:mir\s+)?(?:einen?\s+|ein\s+)?"
            r"(?:interessenten?|prospect|potentiell\w*\s+kunden?)\s+an\b|"
            r"\blege?\s+.+\s+als\s+(?:einen?\s+|ein\s+)?"
            r"(?:interessenten?|prospect|potentiell\w*\s+kunden?)\s+an\b|"
            r"\blege?\s+.+\s+als\s+(?:ansprechpartner|kontakt)\s+(?:bei|von)\s+.+\s+an\b|"
            r"\blege?\s+.+\s+als\s+(?:ansprechpartner|kontakt)\s+an\b|"
            r"\blege?\s+.+\s+mit\s+.+\s+an\b|"
            r"\blege?\s+(?:die\s+|das\s+|den\s+)?firma\s+.+\s+an\b|"
            r"\blege?\s+(?:das\s+)?unternehmen\s+.+\s+an\b|"
            r"\bneuen?\s+(?:interessenten?|prospect|potentiell\w*\s+kunden?)\s+anlegen\b|"
            # „Lege Hassan Yassine an“ (Title-Case Name, kein „Kunden an“)
            r"^\s*lege?\s+(?!mir\b)(?!(?:einen?|ein)\s+kunden?\b)"
            r"[A-ZÄÖÜ][\w\-]+(?:\s+(?:von|van|de|del|di|da|la|le|[A-ZÄÖÜ][\w\-]+)){0,5}"
            r"\s+an\s*$"
            r")"
        ),
        "crm.prospect_create",
        "write",
    ),
    # Zug F Drive Agency-Sales
    (
        re.compile(
            r"(?i)\b("
            r"drive\s+(?:doc|dokument|kurzdoc|notiz)|"
            r"(?:leg|lege|erstell\w*|schreib\w*)\s+(?:ein\s+)?(?:drive\s+)?"
            r"(?:doc|dokument|kurzdoc)|"
            r"kurzdoc\s+(?:anlegen|erstellen)"
            r")\b"
        ),
        "drive.doc_create",
        "write",
    ),
    # Zug I: Zeilen schreiben vor leerem Tabellen-Anlegen
    (
        re.compile(
            r"(?i)\b("
            r"drive\s+(?:tabelle|sheet)\s+(?:schreiben|zeilen)|"
            r"(?:schreib|schreibe)\w*\s+(?:in\s+)?(?:die\s+)?(?:drive\s+)?tabelle|"
            r"tabelle\s+(?:schreiben|zeilen)|"
            r"sheet\s+(?:schreiben|zeilen|rows)|"
            r"drive\s+zeilen"
            r")\b"
        ),
        "drive.sheet_write",
        "write",
    ),
    (
        re.compile(
            r"(?i)\b("
            r"drive\s+(?:tabelle|sheet)|"
            r"(?:leg|lege|erstell\w*)\s+(?:eine?\s+)?(?:drive\s+)?tabelle|"
            r"tabelle\s+(?:anlegen|erstellen)\s+in\s+drive"
            r")\b"
        ),
        "drive.sheet_create",
        "write",
    ),
    (
        re.compile(
            r"(?i)\b("
            r"drive|"
            r"drive[- ]?(?:liste|list|ordner)|"
            r"agency[- ]?sales[- ]?(?:drive|ordner)|"
            r"(?:zeig|zeige)\w*\s+(?:mir\s+)?(?:den\s+)?drive"
            r")\b"
        ),
        "drive.read",
        "read",
    ),
    # Zug D Inbound (Agency-Sales) — before generic sales field
    (
        re.compile(
            r"(?i)\b("
            r"annehmen\s+(?:meta|email|mail|agency)\s*[:#\-]?\s*\d+|"
            r"lead\s+annehmen|"
            r"inbound\s+annehmen|"
            r"annehmen\s+#?(?:meta|email)\-?\d+"
            r")\b"
        ),
        "crm.inbound_accept",
        "write",
    ),
    (
        re.compile(
            r"(?i)\b("
            r"inbound|"
            r"neue\s+leads|"
            r"meta[- ]?leads|"
            r"offene\s+(?:inbound[- ]?)?leads|"
            r"inbound[- ]?liste"
            r")\b"
        ),
        "crm.inbound_read",
        "read",
    ),
    # Zug T: Stage-Move VOR generischem „pipeline“ (sonst frisst Pipeline-Stage den Read)
    (
        re.compile(
            r"(?i)(?:"
            r"\bdeal\s+verschieb\w*\b|"
            r"\b(?:verschieb|rück|ruck)\w*\s+(?:den\s+)?deal\b|"
            r"\bdeal\s+(?:auf|nach)\s+\S+|"
            r"\b(?:stage|phase)\s*[:=]\s*\S+|"
            r"\b(?:stage|phase)\s+\S+\s+bei\b|"
            r"\bpipeline[- ]?stage\b|"
            r"\bauf\s+(?:die\s+)?(?:stage|phase)\s+\S+"
            r")"
        ),
        "crm.deal_stage_update",
        "write",
    ),
    # Second-Manager sales field + Zug C SLA
    (
        re.compile(
            r"(?i)\b("
            r"morgen[- ]?briefing|briefing\s+morgen|lage\s+morgen|manager[- ]?briefing|"
            r"funnel[- ]?review|wochen[- ]?review|wochen[- ]?funnel|verkaufs[- ]?review|"
            r"follow[- ]?up\s*sla|sla\s+heute|nachfass[- ]?sla|"
            r"heiss(?:e)?\s+leads|heiße\s+leads|warme\s+leads|"
            r"welche\s+leads\s+sind\s+(?:heiss|heiß|warm)|"
            r"abend[- ]?debrief|tagesabschluss|abend[- ]?review|"
            r"pipeline\s+heute|feld[- ]?briefing|briefing\s+heute|lage\s+heute|"
            r"stille\s+leads|kalte\s+leads|liegen\s+geblieben|"
            r"pipeline|"
            r"(?:zeig|zeige|zeigen)\w*\s+(?:mir\s+)?(?:die\s+)?pipeline|"
            r"verkaufspipeline|sales[- ]?pipeline|"
            r"welche\s+leads\s+sind\s+(?:offen|still)"
            r")\b"
        ),
        "crm.pipeline_read",
        "read",
    ),
    (
        re.compile(
            r"(?i)\b("
            r"follow[- ]?up\s*(?:vorschlag|skript|tipp)|nachfass[- ]?vorschlag|"
            r"lead[- ]?thread|"
            # Zug Z: Status bei Firma (Street) — bei/von/zu
            r"(?:was\s+ist\s+mit|wie\s+steht(?:'s|\s+es)?\s+(?:um|mit)|"
            r"status\s+(?:von|zu|bei)|firma[- ]?status)\s+\S+|"
            r"(?:aktivit[aä]ten|thread|verlauf)\s+(?:von|für|fuer|bei)\s+\S+|"
            r"(?:zeig|zeige)\w*\s+(?:mir\s+)?(?:den\s+)?(?:verlauf|thread|status)"
            r")\b"
        ),
        "crm.lead_thread",
        "read",
    ),
    (
        re.compile(
            r"(?i)\b("
            r"feld[- ]?close|"
            r"nach\s+dem\s+(?:gespräch|gespraech)|"
            r"(?:notiz|notiere|vermerke)\b|"
            r"speicher\w*\s+(?:eine?\s+)?notiz|"
            r"nächster\s+schritt\s*[:=]"
            r")\b"
        ),
        "crm.note_create",
        "write",
    ),
    (
        re.compile(
            r"(?i)\b("
            r"neuer\s+deal|"
            r"deal\s+wieder\s+öff\w*|"
            r"deal\s+reopen|"
            r"wieder\s+öff\w*\s+(?:den\s+)?deal|"
            r"offenen?\s+deal\s+(?:anlegen|erstellen)"
            r")\b"
        ),
        "crm.deal_open",
        "write",
    ),
    (
        re.compile(
            r"(?i)\b("
            r"won[- ]?ritual|"
            r"lost[- ]?ritual|"
            r"deal\s+(?:gewonnen|verloren|schließen|schliessen)|"
            r"(?:als\s+)?(?:gewonnen|verloren)\s+(?:markieren|setzen)|"
            r"close\s*(?:won|lost)|"
            r"kundennummer\s+(?:vergeben|erzeugen)"
            r")\b"
        ),
        "crm.deal_close",
        "write",
    ),
    (
        re.compile(
            r"(?i)\b("
            r"angebot\s+(?:starter|growth|gastro|basis|wachstum)\s+(?:bei|für|fuer|von)|"
            r"angebot\s+(?:variante|paket)\s+\S+|"
            r"angebot\s+(?:erstellen|anlegen|schreiben|neu)|"
            r"(?:erstelle|lege)\s+(?:mir\s+)?(?:ein\s+)?angebot|"
            r"neues\s+angebot"
            r")\b"
        ),
        "crm.offer_write",
        "write",
    ),
    # Blocked: raw "Kunde anlegen" (use Won/deal_close for conversion)
    (
        re.compile(
            r"(?i)\b("
            r"(?:kunde|kunden|customer)\s+(?:anlegen|erstellen|einrichten)|"
            r"(?:anlegen|erstellen)\s+(?:eines?\s+|einen?\s+)?(?:kunden|kunde|customer)|"
            r"lege\s+(?:mir\s+)?(?:einen?\s+|ein\s+)?kunden?\s+an|"
            r"kundenanlage"
            r")\b"
        ),
        "crm.customer_write",
        "write",
    ),
    # PDF send before plain offer read
    (
        re.compile(
            r"(?i)\b("
            r"(?:schick|sende|send|lade)\w*\s+(?:mir\s+)?(?:das\s+|ein\s+)?angebot\w*\s+(?:als\s+)?pdf|"
            r"angebot\w*\s+(?:als\s+)?pdf|"
            r"pdf\s+(?:vom\s+|des\s+|für\s+|fuer\s+)?angebot|"
            r"sende\s+ang[- ]?\d|"
            r"schick\w*\s+ang[- ]?\d|"
            r"ang[- ]?\d{1,6}\s*(?:als\s+)?pdf"
            r")\b"
        ),
        "crm.offer_pdf_send",
        "read",
    ),
    # CRM company/contact/onboarding read (before generic offer)
    (
        re.compile(
            r"(?i)\b("
            r"(?:kundendaten|firmen(?:daten)?|kontaktdaten|crm[- ]?daten)|"
            r"(?:zeig|zeige|zeigen|lade|laden|anzeigen)\w*\s+(?:mir\s+)?(?:die\s+)?(?:kundendaten|firmen(?:daten)?|kontaktdaten)|"
            r"(?:telefon|e-?mail|mailadresse|handy)\s+(?:von|für|fuer)\s+\S+|"
            r"onboarding(?:[- ]?status|[- ]?übersicht|[- ]?uebersicht)?|"
            r"(?:status|übersicht|uebersicht)\s+(?:des\s+|vom\s+)?onboarding|"
            r"wie\s+(?:weit|steht)\s+(?:das\s+)?onboarding"
            r")\b"
        ),
        "crm.customer_read",
        "read",
    ),
    (
        re.compile(
            r"(?i)\b("
            r"angebot(?:e)?\s+(?:aus\s+dem\s+)?crm|"
            r"(?:zeig|zeige|zeigen|lade|laden|anzeigen)\w*\s+(?:mir\s+)?(?:das\s+|ein\s+)?angebot|"
            r"angebot\s+(?:von|für|fuer)\s+\S|"
            r"welches\s+angebot|"
            r"crm\s*[- ]?\s*angebot|"
            r"\bang[- ]?\d{1,6}\b"
            r")\b"
        ),
        "crm.offer_read",
        "read",
    ),
)

_PROJECT_HINTS = (
    (re.compile(r"(?i)\bgerman\s*golf\s*guide\b|\bGGG\b"), "German Golf Guide", "agency"),
    (re.compile(r"(?i)\bsnack\s*house|SHY001\b"), "Snack House Yassine", "SHY001"),
    (re.compile(r"(?i)\bwebschmiede\b|digitale\s*handwerkskunst\b"), "Webschmiede", "agency"),
    (re.compile(r"(?i)\bbelege?sortier|rechnung(en)?\s*sortier"), "Belegsortierung", "agency"),
)

_ACTION_INTENT_RE = re.compile(
    r"(?i)\b("
    r"trag\s+(das\s+)?ein|eintragen|anlegen|senden|versenden|"
    r"veröffentlichen|veroeffentlichen|löschen|loeschen|"
    r"starte|ausführen|ausfuehren|deploy|posten|"
    r"prüfe\s+live|pruefe\s+live|schau\s+in\s+die\s+logs|"
    r"workflow|n8n|kalender|termin\s+machen|shadowjob"
    r")\b"
)

_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    # Calendar params validated/defaulted in calendar_exec (Hold/Testkalender)
    "calendar.write": (),
    "calendar.create": (),
    "calendar.update": (),
    "calendar.delete": (),
    "calendar.invite": (),
    "calendar.prepare": (),
    "calendar.read": (),
    "calendar.freebusy": (),
    "calendar.availability": (),
    "posting.check": ("projekt", "plattform_oder_speicherort", "zeitraum", "pruefkriterien"),
    "posting.publish": ("projekt", "plattform_oder_speicherort", "inhalt"),
    # blocked at preflight — no param chase
    "email.send": (),
    "n8n.execute": ("workflow", "projekt"),
    "shadow.echo": (),
    "crm.offer_read": ("company",),
    "crm.read": ("company",),
    "crm.customer_read": ("company",),
    "crm.prospect_create": ("company",),
    # to/subject/body validated in inline exec (multiturn)
    "crm.email_send": (),
    # company OR offer_number validated in PDF path (not both required here)
    "crm.offer_pdf_send": (),
    "crm.customer_write": (),
    "crm.pipeline_read": (),
    "crm.lead_thread": ("company",),
    "crm.note_create": ("company",),
    "crm.deal_stage_update": ("company",),
    "crm.deal_open": ("company",),
    "crm.offer_write": ("company",),
    "crm.deal_close": ("company",),
    "crm.inbound_read": (),
    "crm.inbound_accept": (),
    "drive.read": (),
    "drive.list": (),
    "drive.doc_create": (),
    "drive.sheet_create": (),
    "drive.sheet_write": (),
    "drive.write": (),
}

_SM1_CAPS = frozenset(
    {
        "crm.pipeline_read",
        "crm.lead_thread",
        "crm.note_create",
        "crm.deal_stage_update",
        "crm.deal_open",
        "crm.offer_write",
        "crm.deal_close",
    }
)
_INBOUND_CAPS = frozenset({"crm.inbound_read", "crm.inbound_accept"})
_DRIVE_CAPS = frozenset(
    {
        "drive.read",
        "drive.list",
        "drive.doc_create",
        "drive.sheet_create",
        "drive.sheet_write",
        "drive.write",
    }
)
_CAL_CAPS = frozenset(
    {
        "calendar.read",
        "calendar.freebusy",
        "calendar.availability",
        "calendar.prepare",
        "calendar.create",
        "calendar.update",
        "calendar.delete",
        "calendar.invite",
        "calendar.write",
    }
)


@dataclass
class PipelineContext:
    text: str
    chat_id: str
    user_id: str | None = None
    message_id: str | int | None = None
    stage: str = "INTENT_CHECK"
    intent_kind: str = ""  # question | check | prepare | action | control | unclear
    expected_result: str = ""
    is_continuation: bool = False
    kunde: str = ""
    projekt: str = ""
    target_system: str = ""
    capability: str = ""
    action_class: str = ""
    missing_inputs: list[str] = field(default_factory=list)
    extracted: dict[str, str] = field(default_factory=dict)
    preflight: pref.PreflightResult | None = None
    approval_needed: str | None = None
    approval_granted: bool = False
    job: dict[str, Any] | None = None
    blocked_reason: str = ""
    reply: str = ""
    stages_run: list[str] = field(default_factory=list)
    ok: bool = False
    route: str = "pipeline"


def _mark(ctx: PipelineContext, stage: str) -> None:
    ctx.stage = stage
    if stage not in ctx.stages_run:
        ctx.stages_run.append(stage)


def detect_execution_intent(text: str) -> bool:
    """True if message looks like a real action (not pure chat)."""
    t = (text or "").strip()
    if not t:
        return False
    if len(t) < 4:
        return False
    if map_capability(t):
        return True
    return bool(_ACTION_INTENT_RE.search(t))


def map_capability(text: str) -> tuple[str, str] | None:
    """Return (capability, action_class) if text maps to a known capability."""
    t = (text or "").strip()
    if not t:
        return None
    for rx, cap, aclass in _INTENT_CAPABILITY:
        if rx.search(t):
            return cap, aclass
    return None


def extract_customer_from_text(text: str) -> str:
    """Pull company/contact name from offer/CRM phrasing (legacy name)."""
    return extract_company_from_text(text)


def extract_company_from_text(text: str) -> str:
    """Pull company name from offer/CRM phrasing."""
    t = (text or "").strip().rstrip(" .!?…")
    # „Lege Hassan als Ansprechpartner bei Snack House Yassine an“
    m = re.search(
        r"(?i)^\s*lege?\s+.+?\s+als\s+(?:ansprechpartner|kontakt)\s+(?:bei|von)\s+(.+?)\s+an\s*$",
        t,
    )
    if m:
        return m.group(1).strip().strip(" .!?\"'")[:120]
    # „Lege Max Mustermann als Ansprechpartner an“ → Firma fehlt (kein Company-Name)
    if re.search(
        r"(?i)^\s*lege?\s+.+\s+als\s+(?:ansprechpartner|kontakt)\s+an\s*$",
        t,
    ) and not re.search(r"(?i)\b(?:bei|von)\b", t):
        return ""
    # „Lege Hassan Yassine als potentieller Kunde / Interessenten an“
    m = re.search(
        r"(?i)^\s*lege?\s+(.+?)\s+als\s+(?:einen?\s+|ein\s+)?"
        r"(?:interessenten?|prospect|potentiell\w*\s+kunden?)\s+an\s*$",
        t,
    )
    if m:
        name = m.group(1).strip().strip(" .!?\"'")
        if name and not re.search(r"(?i)^(einen?|ein|die|das|den)$", name):
            return name[:120]
    # Prospect create: „Leg Müller Dach GmbH mit Peter Müller an.“
    m = re.search(
        r"(?i)^\s*lege?\s+(.+?)\s+mit\s+.+?\s+an\s*$",
        t,
    )
    if m:
        name = m.group(1).strip().strip(" .!?\"'")
        if name and not re.search(r"(?i)^(einen?|ein|die|das|den)$", name):
            return name[:120]
    m = re.search(
        r"(?i)^\s*lege?\s+(?:die\s+|das\s+|den\s+)?(?:firma|unternehmen)\s+(.+?)\s+an\s*$",
        t,
    )
    if m:
        return m.group(1).strip().strip(" .!?\"'")[:120]
    m = re.search(
        r"(?i)(?:interessent(?:en)?|prospect|potentiell\w*\s+kunde)\s+"
        r"(?:anlegen|erstellen)\s*[:\-]?\s*(.+)$",
        t,
    )
    if m:
        return m.group(1).strip().strip(" .!?\"'")[:120]
    m = re.search(
        r"(?i)lege\s+(?:mir\s+)?(?:einen?\s+|ein\s+)?"
        r"(?:interessenten?|prospect|potentiell\w*\s+kunden?)\s+(.+?)\s+an\s*$",
        t,
    )
    if m:
        return m.group(1).strip().strip(" .!?\"'")[:120]
    # „Lege Hassan Yassine an“ / „Lege Firma B als Interessenten an“ (already covered)
    m = re.search(
        r"(?i)^\s*lege?\s+(?!mir\b)(?!(?:einen?|ein)\s+kunden?\b)(.+?)\s+an\s*$",
        t,
    )
    if m:
        name = m.group(1).strip().strip(" .!?\"'")
        name = re.sub(
            r"(?i)\s+als\s+(?:einen?\s+|ein\s+)?"
            r"(?:interessenten?|prospect|potentiell\w*\s+kunden?)$",
            "",
            name,
        ).strip()
        if name and not re.search(
            r"(?i)^(einen?|ein|die|das|den|kunde|kunden|interessent)",
            name,
        ):
            return name[:120]
    patterns = (
        r"(?i)angebot\w*\s+von\s+(.+?)\s+an\s+[\w.+-]+@",
        r"(?i)angebot(?:e)?\s+(?:von|für|fuer)\s+(.+?)(?:\s+aus\s+dem\s+crm)?\s*$",
        r"(?i)(?:zeig|zeige|schick|sende)\w*\s+(?:mir\s+)?(?:das\s+)?angebot(?:\s+als\s+pdf)?\s+(?:von|für|fuer)\s+(.+?)(?:\s+an\s+[\w.+-]+@|$)",
        r"(?i)(?:kundendaten|firmen(?:daten)?|kontaktdaten|crm[- ]?daten)\s+(?:von|für|fuer)\s+(.+)$",
        r"(?i)(?:telefon|e-?mail|mailadresse|handy)\s+(?:von|für|fuer)\s+(.+)$",
        r"(?i)onboarding(?:[- ]?status|[- ]?übersicht|[- ]?uebersicht)?\s+(?:von|für|fuer|bei)\s+(.+)$",
        r"(?i)(?:was\s+ist\s+mit|wie\s+steht(?:'s|\s+es)?\s+(?:um|mit)|"
        r"status\s+(?:von|zu|bei)|firma[- ]?status(?:\s+(?:von|zu|bei))?)\s+(.+)$",
        # Feld-Close / Notiz: stop before next-step / notiz: / trailing junk
        r"(?i)(?:aktivit[aä]ten|thread|verlauf|feld[- ]?close)\s+(?:von|für|fuer|bei)\s+"
        r"(?:firma\s*[:=]\s*)?(.+?)(?=\s*(?:nächster\s+schritt|naechster\s+schritt|notiz\s*[:=]|note\s*[:=]|\btermin\b|$))",
        r"(?i)notiz\s+bei\s+(?:firma\s*[:=]\s*)?(.+?)(?=\s*(?:nächster\s+schritt|naechster\s+schritt|notiz\s*[:=]|note\s*[:=]|\btermin\b|:)|$)",
        r"(?i)(?:follow[- ]?up\s*(?:vorschlag|skript|tipp)|nachfass[- ]?vorschlag)\s+(?:von|für|fuer|bei)\s+(.+)$",
        r"(?i)angebot\s+(?:starter|growth|gastro|basis|wachstum)\s+(?:bei|für|fuer|von)\s+(.+)$",
        # Zug T: Deal verschieben / Stage … bei Firma
        r"(?i)deal\s+verschieb\w*\s+bei\s+(.+?)(?=\s+(?:auf|nach)\b|$)",
        r"(?i)verschieb\w*\s+(?:den\s+)?deal\s+bei\s+(.+?)(?=\s+(?:auf|nach)\b|$)",
        r"(?i)deal\s+(?:auf|nach)\s+.+?\s+bei\s+(.+)$",
        r"(?i)(?:stage|phase)\s*[:=]\s*.+?\s+bei\s+(.+)$",
        r"(?i)(?:stage|phase)\s+\S+\s+bei\s+(.+)$",
        r"(?i)(?:neuer\s+deal|deal\s+wieder\s+öff\w*|deal\s+reopen|"
        r"wieder\s+öff\w*\s+(?:den\s+)?deal)\s+(?:bei|von|für|fuer)\s+(.+)$",
        r"(?i)(?:won[- ]?ritual|lost[- ]?ritual|deal\s+(?:gewonnen|verloren))\s+(?:bei|von|für|fuer)\s+(.+)$",
        r"(?i)(?:von|für|fuer)\s+(.+?)(?:\s+aus\s+dem\s+crm)?\s*$",
        r"(?i)(?:firma|unternehmen|company)\s*[:=]\s*(.+)$",
        r"(?i)kunde\s*[:=]\s*(.+)$",
        r"(?i)kunden(?:name|nummer)?\s*[:=]\s*(.+)$",
        r"(?i)welches\s+angebot\s+gehört\s+zu\s+(.+)$",
        r"(?i)welches\s+angebot\s+gehoert\s+zu\s+(.+)$",
    )
    for pat in patterns:
        m = re.search(pat, t, re.M)
        if m:
            name = m.group(1).strip().strip(" .!?\"'")
            name = re.split(
                r"(?i)\s*(?:nächster\s+schritt|naechster\s+schritt|notiz\s*[:=]|note\s*[:=]|"
                r"\btermin\b|\bgrund\s*[:=]|\bohne\s+(?:beleg|doc|drive|kurzdoc)\b|"
                r"\bmit\s+(?:beleg|doc|drive)\b)",
                name,
                maxsplit=1,
            )[0].strip()
            name = re.sub(r"(?i)^firma\s*[:=]\s*", "", name).strip()
            if name and not re.search(r"(?i)^(?:dem\s+)?crm$", name):
                if not re.search(r"(?i)angebot|pdf|onboarding|kundendaten", name):
                    return name[:120]
    return ""


def extract_contact_from_text(text: str) -> str:
    """Optional contact from „Leg Firma mit Max Mustermann an“ / Ansprechpartner."""
    t = (text or "").strip().rstrip(" .!?…")
    m = re.search(
        r"(?i)^\s*lege?\s+(.+?)\s+als\s+(?:ansprechpartner|kontakt)\s+(?:bei|von)\s+.+?\s+an\s*$",
        t,
    )
    if m:
        return m.group(1).strip().strip(" .!?\"'")[:120]
    m = re.search(
        r"(?i)^\s*lege?\s+(.+?)\s+als\s+(?:ansprechpartner|kontakt)\s+an\s*$",
        t,
    )
    if m:
        return m.group(1).strip().strip(" .!?\"'")[:120]
    m = re.search(r"(?i)^\s*lege?\s+.+?\s+mit\s+(.+?)\s+an\s*$", t)
    if m:
        return m.group(1).strip().strip(" .!?\"'")[:120]
    return ""


def extract_email_to_from_text(text: str) -> str:
    t = text or ""
    m = re.search(
        r"(?i)(?:e-?mail|mail)\s+an\s+([\w.+-]+@[\w.-]+\.\w+)",
        t,
    )
    if m:
        return m.group(1).strip().lower()
    m = re.search(r"[\w.+-]+@[\w.-]+\.\w+", t)
    return m.group(0).lower() if m else ""


def extract_email_subject_from_text(text: str) -> str:
    m = re.search(
        r"(?i)(?:betreff|subject)\s*[:=]\s*(.+?)(?=\s+(?:text|inhalt|body)\s*[:=]|$)",
        text or "",
        re.S,
    )
    if m:
        return m.group(1).strip().strip(" .!?\"'")[:200]
    return ""


def extract_email_body_from_text(text: str) -> str:
    m = re.search(r"(?i)(?:text|inhalt|body)\s*[:=]\s*(.+)$", text or "", re.S | re.M)
    if m:
        return m.group(1).strip()
    return ""


def extract_offer_number_from_text(text: str) -> str:
    m = re.search(r"(?i)\b(ang[- ]?\d{1,6})\b", text or "")
    if not m:
        return ""
    raw = m.group(1).upper().replace(" ", "").replace("ANG-", "ANG").replace("ANG", "ANG-", 1)
    m2 = re.match(r"(?i)ANG-?(\d+)$", raw.replace("ANG-", "ANG"))
    # Normalize to ANG-<digits>
    digits = re.sub(r"(?i)^ANG-?", "", raw)
    if digits.isdigit():
        return f"ANG-{digits}"
    return raw


def stage_intent_check(ctx: PipelineContext) -> PipelineContext:
    _mark(ctx, "INTENT_CHECK")
    t = ctx.text.strip()
    low = t.lower()

    active = store.get_single_active_for_chat(ctx.chat_id)
    looks_like_new_task = bool(
        detect_execution_intent(t)
        or any(rx.search(t) for rx, *_ in _INTENT_CAPABILITY)
        or any(rx.search(t) for rx, *_ in _PROJECT_HINTS)
    )
    if active and looks_like_new_task:
        # New task while one is running — do not auto-start / no silent project switch
        ctx.intent_kind = "conflict"
        ctx.blocked_reason = "active_job"
        ctx.reply = (
            f"Es läuft bereits Auftrag {active['job_id']} "
            f"({active.get('projekt') or active.get('task_type') or 'ohne Projekt'}, "
            f"Status {active['status']}).\n"
            "Soll ich den alten Job abbrechen oder den neuen vormerken? "
            "Antworte mit „Stop“ oder „vormerken“."
        )
        ctx.ok = False
        return ctx

    # Map capability early so shadow/special intents become actions
    for rx, cap, aclass in _INTENT_CAPABILITY:
        if rx.search(t):
            ctx.capability = cap
            ctx.action_class = aclass
            break

    if re.search(r"(?i)^\s*(was|wie|wer|wo|wann|warum|wieso)\b", t) and not detect_execution_intent(t):
        ctx.intent_kind = "question"
    elif re.search(r"(?i)\b(prüf|pruef|check|schau|status)\b", t) and not re.search(
        r"(?i)\b(eintragen|senden|veröffentlich|löschen)\b", t
    ):
        ctx.intent_kind = "check"
    elif re.search(r"(?i)\b(vorbereiten|entwurf|draft|planen)\b", t):
        ctx.intent_kind = "prepare"
    elif detect_execution_intent(t) or ctx.capability:
        ctx.intent_kind = "action"
    else:
        ctx.intent_kind = "unclear"

    if ctx.intent_kind == "action" and not ctx.capability:
        ctx.intent_kind = "unclear"
        ctx.reply = (
            "Was genau soll ich tun — und für welches Projekt? "
            "Bitte eine konkrete Aktion nennen (z. B. Termin eintragen, Posting prüfen)."
        )
        ctx.ok = False
        return ctx

    ctx.expected_result = {
        "calendar.write": "Termin im Zielkalender angelegt (mit Beleg)",
        "calendar.create": "Termin angelegt (mit Beleg, nur Zielkalender webschmiede/Hold)",
        "calendar.update": "Testtermin geändert",
        "calendar.delete": "Testtermin gelöscht",
        "calendar.invite": "Einladung vorbereitet/gesendet (nur mit Freigabe)",
        "calendar.prepare": "Termin-Payload vorbereitet (ohne Schreibaktion)",
        "calendar.read": "Terminliste gelesen",
        "calendar.freebusy": "Free/Busy geprüft",
        "calendar.availability": "Verfügbarkeit geprüft",
        "email.send": "E-Mail versendet (mit Beleg)",
        "posting.check": "Posting geprüft (mit Befund)",
        "posting.publish": "Beitrag veröffentlicht (mit Beleg)",
        "n8n.execute": "Workflow gestartet und Ergebnis validiert",
        "shadow.echo": "Shadow-Echo abgeschlossen",
        "crm.offer_read": "Aktuelles Angebot aus dem CRM angezeigt",
        "crm.offer_pdf_send": "Angebots-PDF per Telegram gesendet",
        "crm.customer_read": "CRM Kundendaten / Onboarding angezeigt",
        "crm.prospect_create": "Interessent (PROSPECT) im CRM angelegt — kein Kunde",
        "crm.email_send": "Agency-E-Mail an Allowlist-Empfänger gesendet (mit Freigabe)",
        "crm.read": "CRM-Daten gelesen",
        "crm.pipeline_read": "Verkaufspipeline angezeigt",
        "crm.lead_thread": "Lead-Thread / Aktivitäten angezeigt",
        "crm.note_create": "Street-Close: Notiz (+ optional Termin) gespeichert",
        "crm.deal_stage_update": "Deal-Stage verschoben",
        "crm.deal_open": "Offenen Deal angelegt / bestätigt",
        "crm.offer_write": "Angebot (Entwurf) angelegt",
        "crm.deal_close": "Won-/Lost-Ritual (Close + optional Drive-Beleg)",
        "crm.inbound_read": "Offene Agency-Inbound-Leads gelistet",
        "crm.inbound_accept": "Inbound angenommen → Prospect + Follow-up",
        "drive.read": "Agency-Sales Drive gelistet",
        "drive.doc_create": "Kurzdoc im Agency-Sales Drive angelegt",
        "drive.sheet_create": "Tabelle im Agency-Sales Drive angelegt",
        "drive.sheet_write": "Zeilen in Agency-Sales-Tabelle geschrieben",
        "drive.write": "Drive-Schreibaktion im Agency-Sales Root",
        "crm.customer_write": "nicht verfügbar",
    }.get(ctx.capability, "Erwartetes Ergebnis laut Auftrag")

    if ctx.intent_kind in ("question",) and not ctx.capability:
        # Let normal LLM handle pure questions — pipeline not required
        ctx.ok = True
        ctx.route = "passthrough_question"
        ctx.reply = ""
        return ctx

    ctx.ok = True
    return ctx


def stage_project_resolution(ctx: PipelineContext) -> PipelineContext:
    _mark(ctx, "PROJECT_RESOLUTION")
    # CRM offer read/pdf is tenant-scoped, not project-scoped
    if ctx.capability in (
        "crm.offer_read",
        "crm.read",
        "crm.offer_pdf_send",
        "crm.customer_read",
        "crm.prospect_create",
        "crm.email_send",
        "email.send",
        "crm.customer_write",
        *_SM1_CAPS,
        *_INBOUND_CAPS,
        *_DRIVE_CAPS,
        *_CAL_CAPS,
    ):
        if ctx.capability in _CAL_CAPS:
            ctx.projekt = ctx.projekt or "Kalender"
        elif ctx.capability in _DRIVE_CAPS:
            ctx.projekt = ctx.projekt or "Drive"
        else:
            ctx.projekt = ctx.projekt or "CRM"
        ctx.kunde = ctx.kunde or "agency"
        ctx.ok = True
        return ctx

    matches = []
    for rx, name, kunde in _PROJECT_HINTS:
        if rx.search(ctx.text):
            matches.append((name, kunde))
    # dedupe
    uniq = []
    for m in matches:
        if m not in uniq:
            uniq.append(m)
    if len(uniq) > 1:
        names = ", ".join(n for n, _ in uniq)
        ctx.reply = (
            f"Mehrere Projekte möglich ({names}). "
            "Welches Projekt meinst du genau?"
        )
        ctx.ok = False
        ctx.job = _ensure_clarification_job(ctx)
        return ctx
    if len(uniq) == 1:
        ctx.projekt, ctx.kunde = uniq[0]
        ctx.ok = True
        return ctx

    # Action without project — ask once
    if ctx.intent_kind in ("action", "check", "prepare") and ctx.capability != "shadow.echo":
        ctx.reply = "Für welchen Kunden und welches Projekt soll ich das machen?"
        ctx.ok = False
        ctx.job = _ensure_clarification_job(ctx)
        return ctx

    ctx.projekt = ctx.projekt or "unassigned"
    ctx.kunde = ctx.kunde or "unassigned"
    ctx.ok = True
    return ctx


def _extract_inputs(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    # Very conservative keyword extraction — missing → clarification
    date_m = re.search(
        r"(?i)\b(\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?|"
        r"morgen|heute|übermorgen|uebermorgen|"
        r"montag|dienstag|mittwoch|donnerstag|freitag|samstag|sonntag)\b",
        text,
    )
    if date_m:
        out["datum"] = date_m.group(1)
    time_m = re.search(r"(?i)\b(\d{1,2}:\d{2}|\d{1,2}\s*uhr)\b", text)
    if time_m:
        out["uhrzeit_oder_zeitraum"] = time_m.group(1)
        out["zeitraum"] = time_m.group(1)
    title_m = re.search(
        r"(?i)(?:titel|betreff)\s*[:=]\s*(.+?)(?=\s+(?:zeilen|rows|daten|notiz|nächster\s+schritt)\s*[:=]|$)",
        text,
        re.S,
    )
    if title_m:
        out["titel"] = title_m.group(1).strip()[:120]
        out["betreff"] = out["titel"]
    cal_m = re.search(r"(?i)(?:kalender)\s*[:=]\s*(\S+)", text)
    if cal_m:
        out["kalender"] = cal_m.group(1)
    plat_m = re.search(r"(?i)(?:plattform|instagram|facebook|linkedin|speicherort)\s*[:=]?\s*(\S+)", text)
    if plat_m:
        out["plattform_oder_speicherort"] = plat_m.group(1)
    if re.search(r"(?i)\bkriterien\b|\bcheckliste\b", text):
        out["pruefkriterien"] = "genannt"
    if re.search(r"(?i)\b(an|empfaenger|empfänger)\s*[:=]\s*\S+@", text):
        out["empfaenger"] = "genannt"
    if re.search(r"(?i)\binhalt\s*[:=]", text) or len(text) > 80:
        out["inhalt"] = "genannt"
    if re.search(r"(?i)\bworkflow\s*[:=]\s*\S+", text):
        out["workflow"] = "genannt"
    cust = extract_company_from_text(text)
    if cust:
        out["company"] = cust
        out["customer"] = cust  # legacy alias for older turn contexts
    contact = extract_contact_from_text(text)
    if contact:
        out["contact"] = contact
    onum = extract_offer_number_from_text(text)
    if onum:
        out["offer_number"] = onum
    eto = extract_email_to_from_text(text)
    if eto:
        out["to"] = eto
        out["empfaenger"] = eto
    esub = extract_email_subject_from_text(text)
    if esub:
        out["subject"] = esub
        out["betreff"] = esub
    ebody = extract_email_body_from_text(text)
    if ebody:
        out["body"] = ebody
        out["inhalt"] = ebody
    if re.search(
        r"(?i)angebot\s+pdf\s+an|angebot\w*\s+pdf\s+an|"
        r"(?:schick|sende)\w*\s+angebot\w*.*\san\s+[\w.+-]+@|"
        r"pdf\s+angebot\s+an\s+[\w.+-]+@",
        text or "",
    ):
        out["attach_offer_pdf"] = "1"
    return out


def stage_input_validation(ctx: PipelineContext) -> PipelineContext:
    _mark(ctx, "INPUT_VALIDATION")
    ctx.extracted = _extract_inputs(ctx.text)
    if ctx.projekt and ctx.projekt != "unassigned":
        ctx.extracted["projekt"] = ctx.projekt

    intent_guard = tr.validate_intent_consistency(ctx.text, ctx.capability)
    if not intent_guard.ok:
        tr.log_turn_routing(
            chat_id=ctx.chat_id,
            message_id=ctx.message_id,
            job_id=(ctx.job or {}).get("job_id") if ctx.job else None,
            current_intent=intent_guard.current_intent or ctx.capability,
            selected_capability=ctx.capability,
            guard_result=intent_guard.reason,
            final_action=intent_guard.final_action or "block",
        )
        ctx.ok = False
        ctx.blocked_reason = intent_guard.reason
        ctx.reply = (
            "Intent und aktuelle Nachricht passen nicht zusammen — "
            "ich führe keinen Tool-Call aus. Bitte den Auftrag klar neu formulieren."
        )
        return ctx

    current_ent = (
        ctx.extracted.get("company")
        or ctx.extracted.get("customer")
        or ctx.extracted.get("contact")
        or tr.primary_entity(ctx.text)
    )

    # Merge collected params from existing turn context / continuation —
    # never leak a prior company/contact when the current message names another entity.
    if ctx.job:
        existing = tc.load(ctx.job) or {}
        collected = dict(existing.get("collected_parameters") or {})
        prev_ent = tr.previous_entity_from_turn(existing)
        reuse = tr.should_reuse_prior_entity(
            text=ctx.text,
            current_entity=current_ent or "",
            previous_entity=prev_ent,
        )
        tr.log_turn_routing(
            chat_id=ctx.chat_id,
            message_id=ctx.message_id,
            job_id=ctx.job.get("job_id"),
            current_intent=ctx.capability,
            previous_intent=tr.previous_intent_from_turn(existing),
            current_entity=current_ent or "",
            previous_entity=prev_ent,
            context_reused=reuse.context_reused,
            reuse_reason=reuse.reuse_reason or reuse.reason,
            selected_capability=ctx.capability,
            guard_result=reuse.reason or "merge_turn",
            final_action=reuse.final_action or reuse.action,
        )
        for k, v in collected.items():
            if not v or k in ctx.extracted:
                continue
            if k in ("company", "customer", "contact") and current_ent:
                if tr.entities_conflict(current_ent, str(v)):
                    continue  # drop stale entity
            if k in ("company", "customer", "contact") and not current_ent:
                if not reuse.context_reused:
                    continue
            ctx.extracted[k] = str(v)

    # Explicit backref („das Angebot noch einmal“) → last succeeded CRM entity
    if (
        not ctx.extracted.get("company")
        and not ctx.extracted.get("customer")
        and tr.has_backreference(ctx.text)
        and ctx.capability in ("crm.offer_read", "crm.read", "crm.offer_pdf_send", "crm.customer_read")
    ):
        last = store.get_last_crm_entity_for_chat(ctx.chat_id)
        if last and last.get("company"):
            ent_ok = tr.validate_entity_against_message(
                ctx.text, last["company"], allow_backref=True
            )
            if ent_ok.ok:
                ctx.extracted["company"] = last["company"]
                ctx.extracted["customer"] = last["company"]
                tr.log_turn_routing(
                    chat_id=ctx.chat_id,
                    message_id=ctx.message_id,
                    job_id=last.get("job_id"),
                    current_intent=ctx.capability,
                    previous_intent=last.get("capability") or "",
                    current_entity=last["company"],
                    previous_entity=last["company"],
                    context_reused=True,
                    reuse_reason="explicit_backreference_last_job",
                    selected_capability=ctx.capability,
                    guard_result="backref_ok",
                    final_action="reuse_last_crm_entity",
                )

    # Alias: company ↔ customer
    if ctx.extracted.get("company") and not ctx.extracted.get("customer"):
        ctx.extracted["customer"] = ctx.extracted["company"]
    if ctx.extracted.get("customer") and not ctx.extracted.get("company"):
        ctx.extracted["company"] = ctx.extracted["customer"]

    # Stale entity guard for planned main object
    main_ent = ctx.extracted.get("company") or ctx.extracted.get("customer") or ""
    if main_ent:
        ent_guard = tr.validate_entity_against_message(
            ctx.text, main_ent, allow_backref=True
        )
        if not ent_guard.ok:
            tr.log_turn_routing(
                chat_id=ctx.chat_id,
                message_id=ctx.message_id,
                current_intent=ctx.capability,
                current_entity=tr.primary_entity(ctx.text),
                previous_entity=main_ent,
                context_reused=False,
                selected_capability=ctx.capability,
                guard_result=ent_guard.reason,
                final_action="block_stale_entity",
            )
            ctx.extracted.pop("company", None)
            ctx.extracted.pop("customer", None)

    required = _REQUIRED_FIELDS.get(ctx.capability, ())
    missing = [f for f in required if f not in ctx.extracted]
    # PDF: need company OR offer_number
    if ctx.capability == "crm.offer_pdf_send":
        if not ctx.extracted.get("company") and not ctx.extracted.get("offer_number"):
            missing = ["company"]
        else:
            missing = []
    # Offer read by number alone is allowed
    if ctx.capability in ("crm.offer_read", "crm.read") and ctx.extracted.get("offer_number"):
        missing = [f for f in missing if f != "company"]
    ctx.missing_inputs = missing
    if missing:
        from nils_job_runtime import crm_sales_field_exec as sales_exec

        if (
            ctx.capability
            in (
                "crm.offer_read",
                "crm.read",
                "crm.offer_pdf_send",
                "crm.customer_read",
                "crm.prospect_create",
                *_SM1_CAPS,
            )
            and missing == ["company"]
        ):
            from nils_job_runtime import crm_language

            ctx.reply = crm_language.ask_company_prompt()
        else:
            ctx.reply = (
                "Pflichtangaben fehlen: "
                + ", ".join(missing)
                + ". Ohne diese starte ich keinen Ausführungsjob."
            )
        ctx.ok = False
        ctx.job = _ensure_clarification_job(ctx)
        if (
            ctx.capability
            in (
                "crm.offer_read",
                "crm.read",
                "crm.offer_pdf_send",
                "crm.customer_read",
                "crm.prospect_create",
                *_SM1_CAPS,
            )
            and ctx.job
        ):
            if ctx.capability == "crm.offer_pdf_send":
                intent = tc.INTENT_CRM_OFFER_PDF
            elif ctx.capability == "crm.customer_read":
                intent = tc.INTENT_CRM_CUSTOMER_READ
            elif ctx.capability == "crm.prospect_create":
                intent = tc.INTENT_CRM_PROSPECT_CREATE
            elif ctx.capability in _SM1_CAPS:
                intent = sales_exec.intent_for_capability(ctx.capability)
            else:
                intent = tc.INTENT_CRM_GET_OFFER
            turn = tc.empty_context(
                chat_id=ctx.chat_id,
                user_id=ctx.user_id,
                intent=intent,
                missing=list(missing),
                collected={k: v for k, v in ctx.extracted.items()},
                state=tc.STATE_WAITING_FOR_INPUT,
            )
            tc.save(ctx.job["job_id"], turn)
            ctx.job = store.get_job(ctx.job["job_id"])
        return ctx
    ctx.ok = True
    return ctx


def stage_capability_preflight(ctx: PipelineContext) -> PipelineContext:
    _mark(ctx, "CAPABILITY_PREFLIGHT")
    # Persist job in PREFLIGHT if we already have one, else create shell job later
    if ctx.job and ctx.job.get("status") in ("RECEIVED", "NEEDS_CLARIFICATION"):
        try:
            ctx.job = store.transition(
                ctx.job["job_id"],
                "PREFLIGHT",
                extra={
                    "pipeline_stage": "CAPABILITY_PREFLIGHT",
                    "capability": ctx.capability,
                    "current_step": "preflight",
                },
            )
        except Exception:
            log.exception("preflight_transition")

    result = pref.run_preflight(ctx.capability)
    ctx.preflight = result
    ctx.target_system = result.target_system or ctx.target_system

    if not result.may_promise_execution:
        ctx.ok = False
        ctx.blocked_reason = result.outcome
        from nils_job_runtime import promise_guard

        if result.outcome == pref.DISABLED_BY_POLICY or ctx.capability in (
            "crm.customer_write",
            # prospect/sales disabled when cap off — same user-facing text
        ):
            ctx.reply = promise_guard.CAPABILITY_DISABLED_TEXT
        else:
            ctx.reply = (
                f"Preflight: {result.outcome}. {result.detail}\n"
                + promise_guard.NO_ACCESS_TEXT
            )
        if not ctx.job:
            ctx.job = _create_job_shell(ctx, status_after="FAILED")
            try:
                store.update_fields(
                    ctx.job["job_id"],
                    error_category=result.outcome,
                    error_message_redacted=store.redact(result.detail, 200),
                    preflight_result=result.outcome,
                    pipeline_stage="CAPABILITY_PREFLIGHT",
                    finished_at=store.utc_now(),
                )
                ctx.job = store.get_job(ctx.job["job_id"])
            except Exception:
                log.exception("preflight_fail_create")
        else:
            try:
                store.transition(
                    ctx.job["job_id"],
                    "FAILED",
                    extra={
                        "finished_at": store.utc_now(),
                        "error_category": result.outcome,
                        "error_message_redacted": store.redact(result.detail, 200),
                        "preflight_result": result.outcome,
                        "pipeline_stage": "CAPABILITY_PREFLIGHT",
                    },
                )
                ctx.job = store.get_job(ctx.job["job_id"])
            except Exception:
                log.exception("preflight_fail_transition")
        return ctx

    ctx.ok = True
    return ctx


def stage_approval_check(ctx: PipelineContext) -> PipelineContext:
    _mark(ctx, "APPROVAL_CHECK")
    assert ctx.preflight is not None
    # Prospect/E-Mail/Sales-Write: Freigabe läuft im Inline-Exec, nicht hier
    if ctx.capability in (
        "crm.prospect_create",
        "crm.email_send",
        *_SM1_CAPS,
        *_INBOUND_CAPS,
        *_DRIVE_CAPS,
        *_CAL_CAPS,
    ):
        ctx.approval_needed = None
        ctx.ok = True
        return ctx
    need = pref.approval_needed(ctx.action_class, ctx.preflight)
    if ctx.approval_granted:
        need = None
    ctx.approval_needed = need
    if need:
        ctx.ok = False
        ctx.reply = (
            f"Status WAITING_FOR_APPROVAL. Benötigte Freigabe: {need}. "
            "Keine Aktion wird ausgeführt, bis du freigibst "
            "(z. B. „freigabe ja“)."
        )
        if ctx.job:
            try:
                ctx.job = store.transition(
                    ctx.job["job_id"],
                    "WAITING_FOR_APPROVAL",
                    extra={
                        "pipeline_stage": "APPROVAL_CHECK",
                        "approval_required": need,
                        "preflight_result": ctx.preflight.outcome,
                        "progress_message": f"Warte auf Freigabe: {need}",
                    },
                )
            except Exception:
                # create job first if missing
                pass
        else:
            ctx.job = _create_job_shell(ctx, status_after="WAITING_FOR_APPROVAL")
        return ctx
    ctx.ok = True
    return ctx


def stage_job_creation(ctx: PipelineContext) -> PipelineContext:
    _mark(ctx, "JOB_CREATION")
    # One active job per chat
    active = store.get_single_active_for_chat(ctx.chat_id)
    if active and (not ctx.job or active["job_id"] != ctx.job.get("job_id")):
        if active["status"] not in ("NEEDS_CLARIFICATION", "WAITING_FOR_APPROVAL", "PREFLIGHT"):
            ctx.ok = False
            ctx.reply = (
                f"Aktiver Job {active['job_id']} blockiert neue Ausführung. "
                "Stop oder vormerken."
            )
            return ctx

    if not ctx.job:
        ctx.job = _create_job_shell(ctx, status_after="RECEIVED")

    jid = ctx.job["job_id"]
    store.update_fields(
        jid,
        kunde=ctx.kunde,
        projekt=ctx.projekt,
        capability=ctx.capability,
        target_system=ctx.target_system,
        expected_result=ctx.expected_result,
        original_request=store.redact(ctx.text, 500),
        pipeline_stage="JOB_CREATION",
        preflight_result=(ctx.preflight.outcome if ctx.preflight else None),
        approval_required=ctx.approval_needed,
    )

    # CRM read-only text: execute inline — never park in QUEUED (no worker slot)
    if ctx.capability in ("crm.offer_read", "crm.read"):
        return _stage_crm_offer_inline(ctx)

    if ctx.capability == "crm.customer_read":
        return _stage_crm_customer_inline(ctx)

    if ctx.capability == "crm.prospect_create":
        return _stage_crm_prospect_inline(ctx)

    if ctx.capability == "crm.email_send":
        return _stage_crm_email_inline(ctx)

    if ctx.capability in _SM1_CAPS:
        return _stage_crm_sales_field_inline(ctx)

    if ctx.capability in _INBOUND_CAPS:
        return _stage_crm_inbound_inline(ctx)

    if ctx.capability in _DRIVE_CAPS:
        return _stage_drive_inline(ctx)

    if ctx.capability in _CAL_CAPS:
        return _stage_calendar_inline(ctx)

    # CRM PDF send: resolve → QUEUED (live allowlist / shadow=0)
    if ctx.capability == "crm.offer_pdf_send":
        return _stage_crm_offer_pdf_queue(ctx)

    # Move to QUEUED only after all gates
    try:
        job = store.get_job(jid)
        assert job is not None
        if job["status"] == "RECEIVED":
            job = store.transition(jid, "PREFLIGHT", extra={"pipeline_stage": "JOB_CREATION"})
        if job["status"] == "PREFLIGHT":
            job = store.transition(
                jid,
                "QUEUED",
                extra={
                    "queued_at": store.utc_now(),
                    "pipeline_stage": "JOB_CREATION",
                    "progress_message": "In Warteschlange",
                },
            )
        elif job["status"] == "WAITING_FOR_APPROVAL" and ctx.approval_granted:
            job = store.transition(
                jid,
                "QUEUED",
                extra={"queued_at": store.utc_now(), "pipeline_stage": "JOB_CREATION"},
            )
        ctx.job = job
    except Exception as e:
        log.exception("job_creation")
        ctx.ok = False
        ctx.reply = f"Job-Erzeugung fehlgeschlagen: {store.redact(str(e), 120)}"
        return ctx

    ctx.ok = True
    ctx.reply = (
        f"Auftrag {ctx.job['job_id']} angelegt.\n"
        f"Projekt: {ctx.projekt}\n"
        f"Kunde: {ctx.kunde}\n"
        f"Capability: {ctx.capability}\n"
        f"Status: {ctx.job['status']}\n"
        f"Erwartetes Ergebnis: {ctx.expected_result}"
    )
    return ctx


def _stage_crm_offer_inline(ctx: PipelineContext) -> PipelineContext:
    """Inline CRM offer read — no worker queue."""
    from nils_job_runtime import crm_offer_exec

    assert ctx.job
    jid = ctx.job["job_id"]
    job = store.get_job(jid)
    assert job
    if job["status"] == "RECEIVED":
        try:
            job = store.transition(
                jid,
                "PREFLIGHT",
                extra={"pipeline_stage": "EXECUTION", "capability": ctx.capability},
            )
        except Exception:
            log.exception("crm_preflight_transition")

    turn = tc.load(job) or tc.empty_context(
        chat_id=ctx.chat_id,
        user_id=ctx.user_id,
        intent=tc.INTENT_CRM_GET_OFFER,
        collected=dict(ctx.extracted),
        missing=[],
        state=tc.STATE_READY_TO_EXECUTE,
    )
    collected = dict(turn.get("collected_parameters") or {})
    collected.update({k: v for k, v in ctx.extracted.items() if v})
    if ctx.extracted.get("company") or ctx.extracted.get("customer"):
        collected["company"] = ctx.extracted.get("company") or ctx.extracted.get("customer")
        collected["customer"] = collected["company"]
    if ctx.extracted.get("offer_number"):
        collected["offer_number"] = ctx.extracted["offer_number"]
    turn["collected_parameters"] = collected
    turn["missing_parameters"] = []
    turn["state"] = tc.STATE_READY_TO_EXECUTE
    tc.save(jid, turn)

    _mark(ctx, "EXECUTION")
    result = crm_offer_exec.execute_offer_read(job=store.get_job(jid) or job, turn=turn)
    ctx.job = result["job"]
    ctx.reply = result["reply"]
    ctx.ok = bool(result["ok"])
    if result.get("terminal") and result["ok"]:
        _mark(ctx, "RESULT_VALIDATION")
        _mark(ctx, "MEMORY_EVENT")
        _mark(ctx, "FINAL_RESPONSE")
    elif not result.get("terminal"):
        # still waiting (multi company/offer) — clarification, not queued
        ctx.ok = False
        _mark(ctx, "FINAL_RESPONSE")
    else:
        _mark(ctx, "FINAL_RESPONSE")
    return ctx


def _stage_crm_customer_inline(ctx: PipelineContext) -> PipelineContext:
    """Inline CRM company/contact/onboarding read — no worker queue."""
    from nils_job_runtime import crm_customer_exec

    assert ctx.job
    jid = ctx.job["job_id"]
    job = store.get_job(jid)
    assert job
    if job["status"] == "RECEIVED":
        try:
            job = store.transition(
                jid,
                "PREFLIGHT",
                extra={"pipeline_stage": "EXECUTION", "capability": ctx.capability},
            )
        except Exception:
            log.exception("crm_customer_preflight")

    turn = tc.load(job) or tc.empty_context(
        chat_id=ctx.chat_id,
        user_id=ctx.user_id,
        intent=tc.INTENT_CRM_CUSTOMER_READ,
        collected=dict(ctx.extracted),
        missing=[],
        state=tc.STATE_READY_TO_EXECUTE,
    )
    collected = dict(turn.get("collected_parameters") or {})
    collected.update({k: v for k, v in ctx.extracted.items() if v})
    if ctx.extracted.get("company") or ctx.extracted.get("customer"):
        collected["company"] = ctx.extracted.get("company") or ctx.extracted.get("customer")
        collected["customer"] = collected["company"]
    turn["intent"] = tc.INTENT_CRM_CUSTOMER_READ
    turn["collected_parameters"] = collected
    turn["missing_parameters"] = []
    turn["state"] = tc.STATE_READY_TO_EXECUTE
    tc.save(jid, turn)

    _mark(ctx, "EXECUTION")
    result = crm_customer_exec.execute_customer_read(
        job=store.get_job(jid) or job, turn=turn
    )
    ctx.job = result["job"]
    ctx.reply = result["reply"]
    ctx.ok = bool(result["ok"])
    if result.get("terminal") and result["ok"]:
        _mark(ctx, "RESULT_VALIDATION")
        _mark(ctx, "MEMORY_EVENT")
        _mark(ctx, "FINAL_RESPONSE")
    elif not result.get("terminal"):
        ctx.ok = False
        _mark(ctx, "FINAL_RESPONSE")
    else:
        _mark(ctx, "FINAL_RESPONSE")
    return ctx


def _stage_crm_prospect_inline(ctx: PipelineContext) -> PipelineContext:
    """Inline prospect create — Freigabe im Exec, dann Write."""
    from nils_job_runtime import crm_prospect_exec

    assert ctx.job
    jid = ctx.job["job_id"]
    job = store.get_job(jid)
    assert job
    if job["status"] == "RECEIVED":
        try:
            job = store.transition(
                jid,
                "PREFLIGHT",
                extra={"pipeline_stage": "EXECUTION", "capability": ctx.capability},
            )
        except Exception:
            log.exception("crm_prospect_preflight")

    turn = tc.load(job) or tc.empty_context(
        chat_id=ctx.chat_id,
        user_id=ctx.user_id,
        intent=tc.INTENT_CRM_PROSPECT_CREATE,
        collected=dict(ctx.extracted),
        missing=[],
        state=tc.STATE_READY_TO_EXECUTE,
    )
    collected = dict(turn.get("collected_parameters") or {})
    collected.update({k: v for k, v in ctx.extracted.items() if v})
    if ctx.extracted.get("company") or ctx.extracted.get("customer"):
        collected["company"] = ctx.extracted.get("company") or ctx.extracted.get("customer")
        collected["customer"] = collected["company"]
    if ctx.extracted.get("contact"):
        collected["contact"] = ctx.extracted["contact"]
    turn["intent"] = tc.INTENT_CRM_PROSPECT_CREATE
    turn["collected_parameters"] = collected
    turn["state"] = tc.STATE_READY_TO_EXECUTE
    tc.save(jid, turn)

    _mark(ctx, "EXECUTION")
    result = crm_prospect_exec.execute_prospect_create(
        job=store.get_job(jid) or job,
        turn=turn,
        approval_granted=bool(ctx.approval_granted),
    )
    ctx.job = result["job"]
    ctx.reply = result["reply"]
    ctx.ok = bool(result["ok"])
    if result.get("terminal") and result["ok"]:
        _mark(ctx, "RESULT_VALIDATION")
        _mark(ctx, "MEMORY_EVENT")
        _mark(ctx, "FINAL_RESPONSE")
    elif not result.get("terminal"):
        ctx.ok = False
        _mark(ctx, "FINAL_RESPONSE")
    else:
        _mark(ctx, "FINAL_RESPONSE")
    return ctx


def _stage_calendar_inline(ctx: PipelineContext) -> PipelineContext:
    """Inline calendar path (mock/google) with Freigabe + Meeting-Notify."""
    from nils_job_runtime import calendar_exec

    assert ctx.job
    jid = ctx.job["job_id"]
    job = store.get_job(jid)
    assert job
    if job["status"] == "RECEIVED":
        try:
            job = store.transition(
                jid,
                "PREFLIGHT",
                extra={"pipeline_stage": "EXECUTION", "capability": ctx.capability},
            )
        except Exception:
            log.exception("calendar_preflight")

    turn = tc.load(job) or tc.empty_context(
        chat_id=ctx.chat_id,
        user_id=ctx.user_id,
        intent="CALENDAR",
        collected=dict(ctx.extracted),
        missing=[],
        state=tc.STATE_READY_TO_EXECUTE,
    )
    collected = dict(turn.get("collected_parameters") or {})
    collected.update({k: v for k, v in ctx.extracted.items() if v})
    turn["intent"] = "CALENDAR"
    turn["collected_parameters"] = collected
    turn["state"] = tc.STATE_READY_TO_EXECUTE
    tc.save(jid, turn)

    _mark(ctx, "EXECUTION")
    result = calendar_exec.execute_calendar(
        job=store.get_job(jid) or job,
        turn=turn,
        capability=ctx.capability,
        approval_granted=bool(ctx.approval_granted),
        original_text=ctx.text,
    )
    ctx.job = result["job"]
    ctx.reply = result["reply"]
    ctx.ok = bool(result["ok"])
    if result.get("terminal") and result["ok"]:
        _mark(ctx, "RESULT_VALIDATION")
        _mark(ctx, "MEMORY_EVENT")
        _mark(ctx, "FINAL_RESPONSE")
    elif not result.get("terminal"):
        ctx.ok = False
        _mark(ctx, "FINAL_RESPONSE")
    else:
        _mark(ctx, "FINAL_RESPONSE")
    return ctx


def _stage_drive_inline(ctx: PipelineContext) -> PipelineContext:
    """Inline Drive Agency-Sales (Zug F)."""
    from nils_job_runtime import drive_exec

    assert ctx.job
    jid = ctx.job["job_id"]
    job = store.get_job(jid)
    assert job
    if job["status"] == "RECEIVED":
        try:
            job = store.transition(
                jid,
                "PREFLIGHT",
                extra={"pipeline_stage": "EXECUTION", "capability": ctx.capability},
            )
        except Exception:
            log.exception("drive_preflight")

    turn = tc.load(job) or tc.empty_context(
        chat_id=ctx.chat_id,
        user_id=ctx.user_id,
        intent=tc.INTENT_DRIVE,
        collected=dict(ctx.extracted),
        missing=[],
        state=tc.STATE_READY_TO_EXECUTE,
    )
    collected = dict(turn.get("collected_parameters") or {})
    collected.update({k: v for k, v in ctx.extracted.items() if v})
    turn["intent"] = tc.INTENT_DRIVE
    turn["collected_parameters"] = collected
    turn["state"] = tc.STATE_READY_TO_EXECUTE
    tc.save(jid, turn)

    _mark(ctx, "EXECUTION")
    result = drive_exec.execute_drive(
        job=store.get_job(jid) or job,
        turn=turn,
        capability=ctx.capability,
        approval_granted=bool(ctx.approval_granted),
        original_text=ctx.text,
    )
    ctx.job = result["job"]
    ctx.reply = result["reply"]
    ctx.ok = bool(result["ok"])
    if result.get("terminal") and result["ok"]:
        _mark(ctx, "RESULT_VALIDATION")
        _mark(ctx, "MEMORY_EVENT")
        _mark(ctx, "FINAL_RESPONSE")
    elif not result.get("terminal"):
        ctx.ok = False
        _mark(ctx, "FINAL_RESPONSE")
    else:
        _mark(ctx, "FINAL_RESPONSE")
    return ctx


def _stage_crm_inbound_inline(ctx: PipelineContext) -> PipelineContext:
    """Inline Agency Inbound list/accept (Zug D)."""
    from nils_job_runtime import inbound_exec

    assert ctx.job
    jid = ctx.job["job_id"]
    job = store.get_job(jid)
    assert job
    if job["status"] == "RECEIVED":
        try:
            job = store.transition(
                jid,
                "PREFLIGHT",
                extra={"pipeline_stage": "EXECUTION", "capability": ctx.capability},
            )
        except Exception:
            log.exception("crm_inbound_preflight")

    intent = (
        tc.INTENT_CRM_INBOUND_ACCEPT
        if ctx.capability == "crm.inbound_accept"
        else tc.INTENT_CRM_INBOUND_READ
    )
    turn = tc.load(job) or tc.empty_context(
        chat_id=ctx.chat_id,
        user_id=ctx.user_id,
        intent=intent,
        collected=dict(ctx.extracted),
        missing=[],
        state=tc.STATE_READY_TO_EXECUTE,
    )
    collected = dict(turn.get("collected_parameters") or {})
    collected.update({k: v for k, v in ctx.extracted.items() if v})
    turn["intent"] = intent
    turn["collected_parameters"] = collected
    turn["state"] = tc.STATE_READY_TO_EXECUTE
    tc.save(jid, turn)

    _mark(ctx, "EXECUTION")
    result = inbound_exec.execute_inbound(
        job=store.get_job(jid) or job,
        turn=turn,
        capability=ctx.capability,
        approval_granted=bool(ctx.approval_granted),
        original_text=ctx.text,
    )
    ctx.job = result["job"]
    ctx.reply = result["reply"]
    ctx.ok = bool(result["ok"])
    if result.get("terminal") and result["ok"]:
        _mark(ctx, "RESULT_VALIDATION")
        _mark(ctx, "MEMORY_EVENT")
        _mark(ctx, "FINAL_RESPONSE")
    elif not result.get("terminal"):
        ctx.ok = False
        _mark(ctx, "FINAL_RESPONSE")
    else:
        _mark(ctx, "FINAL_RESPONSE")
    return ctx


def _stage_crm_sales_field_inline(ctx: PipelineContext) -> PipelineContext:
    """Inline Second-Manager sales field (pipeline/thread/notes/stage/offer/close)."""
    from nils_job_runtime import crm_sales_field_exec as sales_exec

    assert ctx.job
    jid = ctx.job["job_id"]
    job = store.get_job(jid)
    assert job
    if job["status"] == "RECEIVED":
        try:
            job = store.transition(
                jid,
                "PREFLIGHT",
                extra={"pipeline_stage": "EXECUTION", "capability": ctx.capability},
            )
        except Exception:
            log.exception("crm_sales_preflight")

    intent = sales_exec.intent_for_capability(ctx.capability)
    turn = tc.load(job) or tc.empty_context(
        chat_id=ctx.chat_id,
        user_id=ctx.user_id,
        intent=intent,
        collected=dict(ctx.extracted),
        missing=[],
        state=tc.STATE_READY_TO_EXECUTE,
    )
    collected = dict(turn.get("collected_parameters") or {})
    collected.update({k: v for k, v in ctx.extracted.items() if v})
    turn["intent"] = intent
    turn["collected_parameters"] = collected
    turn["state"] = tc.STATE_READY_TO_EXECUTE
    tc.save(jid, turn)

    _mark(ctx, "EXECUTION")
    result = sales_exec.execute_sales_field(
        job=store.get_job(jid) or job,
        turn=turn,
        capability=ctx.capability,
        approval_granted=bool(ctx.approval_granted),
        original_text=ctx.text,
    )
    ctx.job = result["job"]
    ctx.reply = result["reply"]
    ctx.ok = bool(result["ok"])
    if result.get("terminal") and result["ok"]:
        _mark(ctx, "RESULT_VALIDATION")
        _mark(ctx, "MEMORY_EVENT")
        _mark(ctx, "FINAL_RESPONSE")
    elif not result.get("terminal"):
        ctx.ok = False
        _mark(ctx, "FINAL_RESPONSE")
    else:
        _mark(ctx, "FINAL_RESPONSE")
    return ctx


def _stage_crm_email_inline(ctx: PipelineContext) -> PipelineContext:
    """Inline agency e-mail — Freigabe im Exec, Allowlist, Agency-SMTP."""
    from nils_job_runtime import crm_email_exec

    assert ctx.job
    jid = ctx.job["job_id"]
    job = store.get_job(jid)
    assert job
    if job["status"] == "RECEIVED":
        try:
            job = store.transition(
                jid,
                "PREFLIGHT",
                extra={"pipeline_stage": "EXECUTION", "capability": ctx.capability},
            )
        except Exception:
            log.exception("crm_email_preflight")

    turn = tc.load(job) or tc.empty_context(
        chat_id=ctx.chat_id,
        user_id=ctx.user_id,
        intent=tc.INTENT_CRM_EMAIL_SEND,
        collected=dict(ctx.extracted),
        missing=[],
        state=tc.STATE_READY_TO_EXECUTE,
    )
    collected = dict(turn.get("collected_parameters") or {})
    collected.update({k: v for k, v in ctx.extracted.items() if v})
    turn["intent"] = tc.INTENT_CRM_EMAIL_SEND
    turn["collected_parameters"] = collected
    turn["state"] = tc.STATE_READY_TO_EXECUTE
    tc.save(jid, turn)

    _mark(ctx, "EXECUTION")
    result = crm_email_exec.execute_email_send(
        job=store.get_job(jid) or job,
        turn=turn,
        approval_granted=bool(ctx.approval_granted),
    )
    ctx.job = result["job"]
    ctx.reply = result["reply"]
    ctx.ok = bool(result["ok"])
    if result.get("terminal") and result["ok"]:
        _mark(ctx, "RESULT_VALIDATION")
        _mark(ctx, "MEMORY_EVENT")
        _mark(ctx, "FINAL_RESPONSE")
    elif not result.get("terminal"):
        ctx.ok = False
        _mark(ctx, "FINAL_RESPONSE")
    else:
        _mark(ctx, "FINAL_RESPONSE")
    return ctx


def _stage_crm_offer_pdf_queue(ctx: PipelineContext) -> PipelineContext:
    """Resolve CRM offer then queue live PDF send job."""
    from nils_job_runtime import crm_offer_pdf

    assert ctx.job
    jid = ctx.job["job_id"]
    job = store.get_job(jid)
    assert job
    if job["status"] == "RECEIVED":
        try:
            job = store.transition(
                jid,
                "PREFLIGHT",
                extra={"pipeline_stage": "EXECUTION", "capability": ctx.capability},
            )
        except Exception:
            log.exception("crm_pdf_preflight")

    turn = tc.load(job) or tc.empty_context(
        chat_id=ctx.chat_id,
        user_id=ctx.user_id,
        intent=tc.INTENT_CRM_OFFER_PDF,
        collected=dict(ctx.extracted),
        missing=[],
        state=tc.STATE_READY_TO_EXECUTE,
    )
    collected = dict(turn.get("collected_parameters") or {})
    collected.update({k: v for k, v in ctx.extracted.items() if v})
    turn["intent"] = tc.INTENT_CRM_OFFER_PDF
    turn["collected_parameters"] = collected
    turn["state"] = tc.STATE_READY_TO_EXECUTE
    tc.save(jid, turn)

    _mark(ctx, "EXECUTION")
    resolved = crm_offer_pdf.resolve_for_pdf(job=store.get_job(jid) or job, turn=turn)
    ctx.job = resolved["job"]
    if not resolved.get("ready"):
        ctx.reply = resolved.get("reply") or ""
        ctx.ok = bool(resolved.get("ok"))
        _mark(ctx, "FINAL_RESPONSE")
        return ctx

    # Queue for worker (shadow=0 when live allowlist includes capability)
    live = _live_capabilities()
    shadow = "crm.offer_pdf_send" not in live
    store.update_fields(
        jid,
        shadow=1 if shadow else 0,
        task_type="crm.offer_pdf_send",
        capability="crm.offer_pdf_send",
    )
    try:
        queued = crm_offer_pdf.queue_pdf_job(jid)
    except Exception as e:
        log.exception("pdf_queue")
        ctx.ok = False
        ctx.reply = f"PDF-Job konnte nicht eingereiht werden: {type(e).__name__}"
        return ctx
    ctx.job = queued
    ctx.ok = True
    ctx.reply = (
        f"Auftrag {queued['job_id']} angelegt.\n"
        f"Capability: crm.offer_pdf_send\n"
        f"Status: {queued.get('status')}\n"
        f"Angebot: {(resolved.get('offer') and resolved['offer'].offer_number) or '–'}\n"
        "PDF wird per Telegram gesendet."
    )
    _mark(ctx, "FINAL_RESPONSE")
    return ctx


def _live_capabilities() -> set[str]:
    import os

    raw = os.getenv("NILS_WORKER_LIVE_CAPABILITIES") or ""
    return {p.strip() for p in re.split(r"[,;\s]+", raw) if p.strip()}


def stage_execution_stub(ctx: PipelineContext, *, execute: bool = False) -> PipelineContext:
    """Execution is worker-owned. Pipeline only marks readiness unless execute=True (tests)."""
    _mark(ctx, "EXECUTION")
    if not ctx.job:
        ctx.ok = False
        ctx.reply = "Kein Job — Execution verweigert."
        return ctx
    if ctx.job.get("status") not in ("QUEUED", "RUNNING"):
        ctx.ok = False
        ctx.reply = f"Execution verweigert — Status {ctx.job.get('status')}."
        return ctx
    if not execute:
        # Hand off to worker; do not claim live work beyond queue
        ctx.ok = True
        return ctx
    # Staging-only local echo execution
    jid = ctx.job["job_id"]
    store.transition(
        jid,
        "RUNNING",
        extra={
            "started_at": store.utc_now(),
            "pipeline_stage": "EXECUTION",
            "external_kind": "staging_stub",
            "external_last_step": "stub_start",
            "progress_message": "Staging-Stub läuft",
        },
    )
    ctx.job = store.get_job(jid)
    ctx.ok = True
    return ctx


def stage_result_validation(ctx: PipelineContext, *, evidence: dict[str, Any] | None = None) -> PipelineContext:
    _mark(ctx, "RESULT_VALIDATION")
    if not ctx.job:
        ctx.ok = False
        return ctx
    jid = ctx.job["job_id"]
    evidence = evidence or {}
    expected = ctx.expected_result or ctx.job.get("expected_result") or ""
    ok = bool(evidence.get("success")) and bool(evidence.get("proof"))
    same_project = (
        not ctx.projekt
        or ctx.projekt == "unassigned"
        or evidence.get("projekt", ctx.projekt) == ctx.projekt
    )
    if not ok or not same_project or evidence.get("partial"):
        reason = evidence.get("reason") or "Ergebnis nicht belegt / Teilfehler / Projektmismatch"
        store.transition(
            jid,
            "RESULT_VALIDATION_FAILED",
            extra={
                "finished_at": store.utc_now(),
                "result_validation": "failed",
                "error_message_redacted": store.redact(str(reason), 200),
                "pipeline_stage": "RESULT_VALIDATION",
            },
        )
        ctx.job = store.get_job(jid)
        ctx.ok = False
        ctx.reply = final_response_text(ctx.job, kind="FAILED")
        return ctx
    store.transition(
        jid,
        "COMPLETED",
        extra={
            "finished_at": store.utc_now(),
            "result_validation": "validated",
            "result_reference": store.redact(str(evidence.get("proof")), 300),
            "pipeline_stage": "RESULT_VALIDATION",
            "progress_message": "Abgeschlossen",
        },
    )
    ctx.job = store.get_job(jid)
    ctx.ok = True
    return ctx


def stage_memory_event(ctx: PipelineContext) -> PipelineContext:
    _mark(ctx, "MEMORY_EVENT")
    if ctx.job:
        try:
            con = store.connect()
            try:
                store._event(
                    con,
                    ctx.job["job_id"],
                    "memory",
                    store.redact(
                        f"stage={ctx.stage};projekt={ctx.projekt};status={ctx.job.get('status')}",
                        200,
                    ),
                )
                con.commit()
            finally:
                con.close()
        except Exception:
            log.exception("memory_event")
    ctx.ok = True
    return ctx


def stage_final_response(ctx: PipelineContext) -> PipelineContext:
    _mark(ctx, "FINAL_RESPONSE")
    if ctx.job and ctx.job.get("status") in ("COMPLETED", "SUCCEEDED"):
        ctx.reply = final_response_text(ctx.job, kind="COMPLETED")
    elif ctx.job and ctx.job.get("status") == "CANCELLED":
        ctx.reply = final_response_text(ctx.job, kind="CANCELLED")
    elif ctx.job and ctx.job.get("status") in (
        "FAILED",
        "TIMEOUT",
        "TIMED_OUT",
        "RESULT_VALIDATION_FAILED",
    ):
        ctx.reply = final_response_text(ctx.job, kind="FAILED")
    elif not ctx.reply and ctx.job:
        ctx.reply = (
            f"job_id={ctx.job['job_id']} | Projekt={ctx.projekt or '–'} | "
            f"Status={ctx.job['status']} | {ctx.job.get('progress_message') or ''}"
        )
    ctx.ok = True
    return ctx


def final_response_text(job: dict[str, Any] | None, *, kind: str) -> str:
    if not job:
        return "Kein Job."
    jid = job.get("job_id")
    projekt = job.get("projekt") or "–"
    kunde = job.get("kunde") or "–"
    if kind == "COMPLETED":
        return (
            f"COMPLETED {jid}\n"
            f"Kunde/Projekt: {kunde} / {projekt}\n"
            f"Ergebnis: {job.get('expected_result') or '–'}\n"
            f"Beleg: {job.get('result_reference') or '–'}\n"
            f"Offen: {job.get('progress_message') or 'keine'}"
        )
    if kind == "CANCELLED":
        return (
            f"CANCELLED {jid}\n"
            f"Abgebrochen: {job.get('task_summary') or job.get('original_request') or '–'}\n"
            f"Teilaktionen: {job.get('external_last_step') or 'keine nachgewiesen'}"
        )
    return (
        f"FAILED {jid}\n"
        f"Schritt: {job.get('pipeline_stage') or job.get('current_step') or '–'}\n"
        f"Ursache: {job.get('error_message_redacted') or job.get('error_category') or '–'}\n"
        f"Nächster Schritt: jobinspect {jid} oder Auftrag neu formulieren."
    )


def _ensure_clarification_job(ctx: PipelineContext) -> dict[str, Any]:
    if ctx.job:
        try:
            return store.transition(
                ctx.job["job_id"],
                "NEEDS_CLARIFICATION",
                extra={
                    "pipeline_stage": ctx.stage,
                    "progress_message": ctx.reply[:200],
                    "kunde": ctx.kunde or None,
                    "projekt": ctx.projekt or None,
                    "capability": ctx.capability or None,
                },
            )
        except Exception:
            return ctx.job
    return _create_job_shell(ctx, status_after="NEEDS_CLARIFICATION")


def _shadow_task_type(text: str, capability: str) -> str:
    """Map shadowjob subtypes to worker HANDLERS keys (not capability ids)."""
    m = re.match(
        r"(?i)^\s*shadowjob\s+(echo|steps|fail|block|heartbeat_long)\b",
        text or "",
    )
    if m:
        return m.group(1).lower()
    if capability == "shadow.echo":
        return "echo"
    if capability in ("crm.offer_read", "crm.read"):
        return "crm.offer_read"
    if capability == "crm.customer_read":
        return "crm.customer_read"
    if capability == "crm.prospect_create":
        return "crm.prospect_create"
    if capability == "crm.email_send":
        return "crm.email_send"
    if capability == "crm.offer_pdf_send":
        return "crm.offer_pdf_send"
    if capability in _SM1_CAPS:
        return capability
    return capability or "control_plane"


def _create_job_shell(ctx: PipelineContext, *, status_after: str) -> dict[str, Any]:
    ttype = _shadow_task_type(ctx.text, ctx.capability)
    timeout = 120 if ttype == "heartbeat_long" else (30 if ttype == "block" else 900)
    live = _live_capabilities()
    is_live = bool(ctx.capability and ctx.capability in live)
    job = store.create_job(
        task_type=ttype,
        task_summary=(ctx.text or "")[:400],
        telegram_chat_id=ctx.chat_id,
        telegram_user_id=ctx.user_id,
        telegram_message_id=ctx.message_id,
        timeout_seconds=timeout,
        shadow=not is_live,
        max_retries=0,
    )
    store.update_fields(
        job["job_id"],
        kunde=ctx.kunde or None,
        projekt=ctx.projekt or None,
        capability=ctx.capability or None,
        target_system=ctx.target_system or None,
        expected_result=ctx.expected_result or None,
        original_request=store.redact(ctx.text, 500),
        pipeline_stage=ctx.stage,
    )
    if status_after != "RECEIVED" and job.get("status") == "RECEIVED":
        try:
            job = store.transition(
                job["job_id"],
                status_after,
                extra={"pipeline_stage": ctx.stage, "progress_message": (ctx.reply or "")[:200]},
            )
        except Exception:
            log.exception("shell_status")
            job = store.get_job(job["job_id"]) or job
    return job


def run_pipeline(
    *,
    text: str,
    chat_id: str,
    user_id: str | None = None,
    message_id: str | int | None = None,
    approval_granted: bool = False,
    execute_stub: bool = False,
    evidence: dict[str, Any] | None = None,
) -> PipelineContext:
    """Run stages 1–6 always for action intents; 7–10 when execute_stub/evidence set."""
    ctx = PipelineContext(
        text=text or "",
        chat_id=str(chat_id),
        user_id=user_id,
        message_id=message_id,
        approval_granted=approval_granted,
    )

    ctx = stage_intent_check(ctx)
    if ctx.route == "passthrough_question":
        ctx.stages_run = list(PIPELINE_STAGES[:1])
        return ctx
    if not ctx.ok:
        _mark(ctx, "FINAL_RESPONSE")
        return ctx

    for stage_fn in (
        stage_project_resolution,
        stage_input_validation,
        stage_capability_preflight,
        stage_approval_check,
        stage_job_creation,
    ):
        ctx = stage_fn(ctx)
        if not ctx.ok:
            _mark(ctx, "FINAL_RESPONSE")
            return ctx
        # CRM inline path already produced final reply
        if (
            ctx.capability
            in (
                "crm.offer_read",
                "crm.read",
                "crm.customer_read",
                "crm.prospect_create",
                "crm.email_send",
                *_SM1_CAPS,
                *_INBOUND_CAPS,
                *_DRIVE_CAPS,
                *_CAL_CAPS,
            )
            and "FINAL_RESPONSE" in ctx.stages_run
        ):
            return ctx

    if execute_stub:
        ctx = stage_execution_stub(ctx, execute=True)
        if not ctx.ok:
            _mark(ctx, "FINAL_RESPONSE")
            return ctx
        ev = evidence or {
            "success": True,
            "proof": f"staging-stub:{ctx.job and ctx.job.get('job_id')}",
            "projekt": ctx.projekt,
        }
        ctx = stage_result_validation(ctx, evidence=ev)
        ctx = stage_memory_event(ctx)
        ctx = stage_final_response(ctx)
    else:
        _mark(ctx, "EXECUTION")  # handed to worker — stage recorded, not skipped
        ctx.stages_run.append("RESULT_VALIDATION")  # pending
        ctx.stages_run.append("MEMORY_EVENT")
        ctx = stage_final_response(ctx)

    return ctx
