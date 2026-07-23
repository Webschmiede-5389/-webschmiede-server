# -*- coding: utf-8 -*-
"""Nils Guided Mode = Cursor-Level: klären, führen, erst dann umsetzen.

Gilt für Bau, Ops, Sales, Mails, größere Ideen – nicht nur Code.
"""
from __future__ import annotations

import re
from typing import Any

# Überspringen: Christian will sofort Aktion
SKIP_RE = re.compile(
    r"\b("
    r"ohne\s+fragen|direkt\s+(bau|mach|los|umsetzen)|keine\s+rückfrage|keine\s+rueckfrage|"
    r"einfach\s+mach|skip\s+discovery|sofort\s+umsetzen|keine\s+diskussion|"
    r"guided\s+aus|führungsmodus\s+aus"
    r")\b",
    re.I,
)

# Kurze Status-/Kommando-Pfade: kein Guided
COMMAND_EXACT = frozenset({
    "hilfe", "help", "inventar", "tools", "budget", "kosten", "tagesreport",
    "status", "hirnwächter", "hirnwaechter", "kostenwächter", "kostenwaechter",
    "ux", "ux gate", "fact gate", "gedächtnis", "ping", "ok", "danke", "thanks",
})

WORK_RE = re.compile(
    r"\b("
    r"bau|baue|bauen|implementier|programmier|website|landing|portal|feature|"
    r"wir\s+wollen|lass\s+uns|mach\s+(mal\s+)?(eine|ein|das|die|mir)|optimiere|umbau|"
    r"neue\s+seite|app\s+|cursor:|einrichten|aufsetzen|umstellen|ändern|aendern|"
    r"mail\s+an|schreib\s+(eine\s+)?mail|angebot|onboarding|deploy|live\s+nehmen|"
    r"kunden|sms|whatsapp|stripe|domain|bewertung|tischaufsteller|"
    r"wie\s+soll(en)?\s+wir|was\s+meinst\s+du\s+zu|strategie|nächster\s+schritt|"
    r"naechster\s+schritt|planen\s+wir|idee\s+für|idee\s+fuer|konzept|"
    r"reparier|fix|schau\s+dir|recherch|analysier"
    r")\b",
    re.I,
)

YES_GO = frozenset({
    "ja", "yes", "ok", "okay", "mach", "mach das", "los", "so umsetzen",
    "bau das", "umsetzen", "freigabe", "bestätigen", "bestaetigen", "go",
    "machen", "leg los", "loslegen", "passt so", "einverstanden", "mach weiter",
})

GUIDED_POLICY = (
    "=== CURSOR-LEVEL FÜHRUNG (Pflicht) ===\n"
    "Du führst Christian wie ein guter Coding-Agent im Chat:\n"
    "1) Kurz spiegeln was du verstanden hast (1 Satz).\n"
    "2) Wenn unklar oder riskant: 1–3 gezielte Fragen (nicht 10).\n"
    "3) 1–2 konkrete Verbesserungsvorschläge / bessere Variante.\n"
    "4) Klarer nächster Schritt: was du tun würdest, was du von ihm brauchst.\n"
    "5) Teure/irreversible Dinge (Mail senden, Cursor/Deploy, Käufe, Live-Änderungen) "
    "NIE ohne Freigabe. Sag wörtlich dass er mit „mach das“ oder „ja“ freigibt "
    "oder die Fragen beantwortet.\n"
    "6) Smalltalk/Wetter/kurze Faktfrage: normal antworten, kein Verhör.\n"
    "7) Struktur ohne Agentur-Listen: kurze Absätze, Telegram-Ton.\n"
    "8) Keine Fake-Minuten. Vor „fertig“: Fact+UX-Gate.\n"
    "=== ENDE FÜHRUNG ==="
)


def guided_policy(*, short: bool = False) -> str:
    if short:
        return (
            "Cursor-Level: verstehen → ggf. 1–3 Fragen + 1–2 Vorschläge → "
            "nächster Schritt. Bau/Mail/Deploy nur nach Freigabe („mach das“/„ja“)."
        )
    return GUIDED_POLICY


def skip_guided(text: str) -> bool:
    return bool(SKIP_RE.search(text or ""))


def is_go_confirm(text: str) -> bool:
    n = re.sub(r"\s+", " ", (text or "").lower().strip())
    if n in YES_GO:
        return True
    if any(n.startswith(p) for p in ("mach das", "bau das", "so umsetzen", "leg los", "mach weiter")):
        return True
    return False


def classify_intent(text: str) -> str:
    t = (text or "").lower()
    try:
        import nils_cursor_bridge as bridge

        if bridge.looks_like_coding_task(text or "") or "cursor:" in t:
            return "build"
    except Exception:
        pass
    if any(x in t for x in ("mail an", "schick mail", "sende mail", "schreib mail")):
        return "mail"
    if any(x in t for x in ("angebot", "onboarding", "meeting", "sales", "deal")):
        return "sales"
    if any(x in t for x in ("server", "deploy", "guardian", "cron", "dns", "nginx", "watchdog")):
        return "ops"
    if any(x in t for x in ("recherch", "schau dir", "analysier", "firma", "konkurrenz")):
        return "research"
    if any(x in t for x in ("bau", "website", "portal", "programmier", "landing", "app ")):
        return "build"
    if any(x in t for x in ("idee", "strategie", "wie sollen wir", "was meinst du")):
        return "idea"
    return "work"


def needs_guidance(text: str, tools: list[dict[str, Any]] | None = None) -> bool:
    """Wann Guided-Turn (Fragen+Vorschläge) vor Aktion."""
    raw = (text or "").strip()
    if len(raw) < 16:
        return False
    if skip_guided(raw):
        return False
    low = re.sub(r"\s+", " ", raw.lower())
    if low in COMMAND_EXACT or low.startswith("merk dir:") or low.startswith("vergiss:"):
        return False
    if low.startswith("ux check") or low.startswith("cursor status"):
        return False

    tools = tools or []
    names = {t.get("name") for t in tools}
    # Riskante / Bau-Tools → immer führen
    if names & {"cursor_code", "send_mail", "send_offer", "send_onboarding", "sales_invite", "sales_freigabe"}:
        return True
    if "cursor_code" in names:
        return True
    # Substanzielle Arbeitssprache
    if WORK_RE.search(raw) and len(raw) >= 24:
        return True
    # Lange Aufträge ohne Fragezeichen oft Arbeitswunsch
    if len(raw) >= 80 and not raw.rstrip().endswith("?"):
        if any(x in low for x in ("soll", "müssen", "muessen", "brauche", "mach", "bitte", "können", "koennen")):
            return True
    return False


def run_guided(task: str, *, intent: str | None = None) -> dict[str, Any]:
    """Cursor-Level Discovery: führen, noch nicht ausführen."""
    task = (task or "").strip()
    if not task:
        return {"ok": False, "error": "task_empty"}
    kind = intent or classify_intent(task)

    import llm_client as llm
    import human_voice as voice

    kind_hint = {
        "build": "Es geht um Bauen/Website/Code. Noch kein Cursor starten.",
        "mail": "Es geht um eine Mail. Noch nicht senden.",
        "sales": "Sales/Angebot/Onboarding. Noch nichts rausschicken.",
        "ops": "Ops/Server. Erst klären, dann vorsichtig.",
        "research": "Recherche: sag was du prüfen würdest, frag was fehlt.",
        "idea": "Idee/Strategie: sparre, priorisiere, schlage einen kleinen nächsten Schritt vor.",
        "work": "Allgemeiner Auftrag: klären und führen.",
    }.get(kind, "Auftrag klären und führen.")

    system = voice.nils_system(
        " Telegram. CURSOR-LEVEL Guided-Modus. NOCH NICHT ausführen, keine Risk-Tools starten. "
        + guided_policy(short=False)
        + f" Intent: {kind}. {kind_hint} "
        "Antwortformat (ohne fette Überschriften): "
        "Verständnis (1 Satz). Dann Fragen. Dann Vorschläge. Dann: „Wenn’s passt: mach das / ja.“ "
        "Deutsch, Telegram, menschlich.",
        fast=False,
    )
    r = llm.chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Auftrag von Christian:\n{task[:2200]}"},
        ],
        max_tokens=750,
        temperature=0.4,
        timeout=55,
        route="A",
    )
    if not r.get("ok") or not (r.get("reply") or "").strip():
        text = (
            f"Kurz check ich, ob ich dich richtig verstehe: {task[:180]}\n\n"
            f"Bevor ich loslege:\n"
            f"1) Was genau soll am Ende anders sein?\n"
            f"2) Für wen (du, Kunde, Endkunde)?\n"
            f"3) Pflicht jetzt vs. später?\n\n"
            f"Vorschlag: kleinster sinnvoller Schritt zuerst, dann Feinschliff.\n"
            f"Antwort auf die Fragen oder „mach das“."
        )
        return {
            "ok": True,
            "text": text,
            "intent": kind,
            "pending": {
                "phase": "discovery",
                "tool": "discovery",
                "task": task,
                "intent": kind,
            },
        }

    reply = (r.get("reply") or "").strip()
    if "mach das" not in reply.lower():
        reply += "\n\nWenn’s passt: „mach das“ oder „ja“. Sonst kurz die Fragen beantworten."
    return {
        "ok": True,
        "text": reply,
        "intent": kind,
        "pending": {
            "phase": "discovery",
            "tool": "discovery",
            "task": task,
            "intent": kind,
        },
        "llm_model": r.get("model"),
    }


def merge_task_after_answers(original: str, answers: str) -> str:
    return (
        f"{(original or '').strip()}\n\n"
        f"## Klärung von Christian\n{(answers or '').strip()}"
    )[:4000]


def execute_after_go_system(intent: str) -> str:
    return (
        "Christian hat freigegeben (Guided → Go). "
        "Jetzt konkret umsetzen bzw. klar antworten. "
        "Keine weiteren Meta-Fragen außer echten Blockern. "
        f"Intent war: {intent}. "
        "Bei Code/Website: Tool cursor_code nutzen (bereits freigegeben). "
        "Bei Mail: nur senden wenn Empfänger+Inhalt klar, sonst eine gezielte Frage. "
        "Fact+UX-Gate beachten bevor du „fertig“ sagst."
    )


# Rückwärtskompatibilität für alte Imports
def looks_like_build(text: str) -> bool:
    return classify_intent(text) == "build" or needs_guidance(text)


def skip_discovery(text: str) -> bool:
    return skip_guided(text)


def is_build_confirm(text: str) -> bool:
    return is_go_confirm(text)


def run_discovery(task: str) -> dict[str, Any]:
    return run_guided(task)
