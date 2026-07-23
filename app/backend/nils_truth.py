# -*- coding: utf-8 -*-
"""Halluzinations-Versicherung für Nils.

Regel: Nur belegte Fakten. Unbekannt = ehrlich sagen oder nachfragen.
Kein Erfinden von Kunden, Zahlen, Status, Mails, Anrufen, Features.
"""
from __future__ import annotations

import re
from typing import Any

# In jeden System-Prompt / Tool-Prompt hängen
FACT_POLICY = (
    "HALLUZINATIONS-VERBOT (hart): "
    "Erfinde nichts. Nutze nur Fakten aus mitgeliefertem Kontext "
    "(Tools, Gedächtnis, Live-Suche, Brain-Ergebnis, Nutzertext). "
    "Unklar oder nicht belegt → sag „weiß ich nicht / nicht geprüft“ und frag nach. "
    "Keine erfundenen: Kundenstatus, Preise, Umsatz, Termine, Mails, Anrufe, "
    "Deploy-Ergebnisse, n8n-Läufe, PR-Links, Feature-„ist live“, API-Keys. "
    "Keine Schein-Genauigkeit (erfundene Prozent, Euro, Datumsangaben). "
    "Wenn Tools nichts geliefert haben: nicht so tun als hättest du geprüft. "
    "Meinungen/Ideen klar als Vorschlag kennzeichnen, nicht als Fakt."
)

FACT_POLICY_SHORT = (
    "Nur belegte Fakten. Unbekannt ehrlich sagen. Nichts erfinden "
    "(Status, Preise, Mails, Deploys, Links)."
)

# Typische Halluzinations-Fallen in Antworten (weich warnen, nicht zensieren)
_CLAIM_PATTERNS = (
    re.compile(r"\b(?:ich habe|habe ich)\s+(?:gerade\s+)?(?:angerufen|geschrieben|gesendet|deployt)\b", re.I),
    re.compile(r"\b(?:ist|sind)\s+(?:definitiv|garantiert|zu\s+100\s*%|sicher)\s+live\b", re.I),
    re.compile(r"\bPR\s*#?\d{2,}\b"),
    re.compile(r"https?://github\.com/[^\s]+/pull/\d+", re.I),
)


def policy_for_prompt(*, short: bool = False) -> str:
    return FACT_POLICY_SHORT if short else FACT_POLICY


def grounding_block(
    *,
    memory: str = "",
    tool_notes: list[str] | None = None,
    web: str = "",
    media: list[str] | None = None,
    plan_header: str = "",
    extra: str = "",
) -> str:
    """Nur-Quellen-Block fürs LLM. Leer = Modell darf nichts „wissen“."""
    parts: list[str] = [
        "=== BELEGTE QUELLEN (nur das gilt als Fakt) ===",
        FACT_POLICY_SHORT,
    ]
    if plan_header:
        parts.append("Plan:\n" + plan_header.strip())
    if memory:
        parts.append("Gedächtnis:\n" + memory.strip()[:2000])
    if web:
        parts.append("Live-Suche:\n" + web.strip()[:2000])
    for m in media or []:
        if m:
            parts.append("Medien:\n" + str(m)[:1200])
    for n in tool_notes or []:
        if n:
            parts.append("Tool:\n" + str(n)[:1500])
    if extra:
        parts.append(extra.strip()[:1500])
    if len(parts) <= 2:
        parts.append(
            "(Keine Tool-/Live-Fakten geliefert. Nur Nutzernachricht + ehrliche Unsicherheit.)"
        )
    parts.append("=== ENDE QUELLEN ===")
    return "\n\n".join(parts)


def soft_hallucination_flags(reply: str) -> list[str]:
    """Leichte Heuristik: verdächtige Behauptungen ohne Quellen-Check."""
    text = reply or ""
    flags = []
    for pat in _CLAIM_PATTERNS:
        if pat.search(text):
            flags.append(pat.pattern[:60])
    return flags[:5]


def honesty_footer(*, had_tools: bool, had_web: bool) -> str:
    if had_tools or had_web:
        return ""
    return (
        "\n\n(Hinweis: Das war ohne frischen Tool-/Live-Check. "
        "Wenn du Status/Zahlen brauchst, sag Bescheid, dann prüfe ich live.)"
    )


def wrap_system(base: str, *, short: bool = False) -> str:
    return (base or "").rstrip() + " " + policy_for_prompt(short=short)
