# -*- coding: utf-8 -*-
"""Block false live/execution promises unless a real job is QUEUED/RUNNING."""
from __future__ import annotations

import re
from typing import Any

from nils_job_runtime.model import may_claim_live

LIVE_PROMISE_RE = re.compile(
    r"(?i)\b("
    r"ich\s+prüfe\s+jetzt\s+live|"
    r"ich\s+pruefe\s+jetzt\s+live|"
    r"ich\s+fange\s+direkt\s+an|"
    r"ich\s+schaue\s+mir\s+die\s+logs\s+an|"
    r"ich\s+schau(?:e)?\s+jetzt|"
    r"ich\s+hole\s+(?:dir\s+)?(?:das\s+)?dokument|"
    r"ich\s+hol\s+(?:dir\s+)?(?:das\s+)?dokument|"
    r"einen\s+moment|"
    r"ich\s+trage\s+das\s+ein|"
    r"ich\s+veröffentliche\s+das|"
    r"ich\s+veroeffentliche\s+das|"
    r"ich\s+starte\s+jetzt|"
    r"ich\s+führe\s+das\s+jetzt\s+aus|"
    r"ich\s+fuehre\s+das\s+jetzt\s+aus|"
    r"bin\s+schon\s+dran|"
    r"recherchiere\s+im\s+hintergrund|"
    # Offer / customer / PDF promises — only with real QUEUED/RUNNING job
    r"ich\s+erstelle\s+(?:das\s+)?angebot|"
    r"ich\s+lege\s+(?:ihn|sie|den|die|einen?\s+)?(?:kunden|interessenten)\s+an|"
    r"ich\s+lege\s+(?:den\s+)?kunden\s+an|"
    r"ich\s+lege\s+(?:einen\s+)?kunden\s+an|"
    r"ich\s+lege\s+(?:den\s+)?interessenten\s+an|"
    r"ich\s+lege\s+(?:einen\s+)?interessenten\s+an|"
    r"ich\s+lege\s+(?:das\s+)?angebot\s+an|"
    r"ich\s+sende\s+dir\s+(?:gleich\s+)?(?:das\s+)?pdf|"
    r"ich\s+schicke\s+dir\s+(?:gleich\s+)?(?:das\s+)?pdf|"
    r"ich\s+sende\s+(?:dir\s+)?(?:gleich\s+)?(?:die\s+)?(?:e-?mail|mail)|"
    r"ich\s+schreibe\s+(?:dir\s+)?(?:gleich\s+)?(?:eine?\s+)?(?:e-?mail|mail)|"
    r"ich\s+sende\s+(?:dir\s+)?(?:gleich\s+)?das\s+angebot|"
    r"ich\s+kümmere\s+mich\s+darum|"
    r"ich\s+kuemmere\s+mich\s+darum|"
    r"ich\s+mache\s+das\s+(?:gleich|sofort|jetzt)|"
    r"pdf\s+kommt\s+gleich|"
    r"ich\s+erstelle\s+(?:dir\s+)?(?:gleich\s+)?(?:ein\s+)?pdf"
    r")\b"
)

NO_ACCESS_TEXT = (
    "Ich habe aktuell keinen funktionsfähigen Zugriff auf dieses System "
    "und kann die Aktion nicht ausführen."
)

CAPABILITY_DISABLED_TEXT = "Diese Aktion kann ich aktuell noch nicht ausführen."

POLICY_FOR_PROMPT = (
    "AUSFÜHRUNGS-ZUSAGE-VERBOT: Formulierungen wie „Ich prüfe jetzt live“, "
    "„Ich erstelle das Angebot“, „Ich sende dir gleich das PDF“, "
    "„Ich lege den Kunden an“, „Ich kümmere mich darum“ "
    "nur wenn eine echte job_id existiert, der Intent erkannt wurde, "
    "die Capability produktiv verfügbar ist, Preflight OK und Status "
    "QUEUED oder RUNNING. "
    "Ohne Nachweis: klar ablehnen — keine LLM-Zusage ohne Job. "
    "Fehlende Capability: „Diese Aktion kann ich aktuell noch nicht ausführen.“"
)


def contains_live_promise(text: str) -> bool:
    return bool(LIVE_PROMISE_RE.search(text or ""))


def may_use_live_language(*, job: dict[str, Any] | None) -> bool:
    if not job:
        return False
    if not job.get("job_id"):
        return False
    return may_claim_live(job.get("status"))


def sanitize_reply(
    reply: str,
    *,
    job: dict[str, Any] | None = None,
    force_no_access: bool = False,
    capability_disabled: bool = False,
) -> str:
    """Strip or replace false execution promises."""
    t = (reply or "").strip()
    if capability_disabled:
        return CAPABILITY_DISABLED_TEXT
    if force_no_access:
        if contains_live_promise(t) or not t:
            return NO_ACCESS_TEXT
    if contains_live_promise(t) and not may_use_live_language(job=job):
        # Replace the whole reply if it is primarily a fake promise
        if len(t) < 280 or LIVE_PROMISE_RE.match(t):
            return NO_ACCESS_TEXT
        return (
            NO_ACCESS_TEXT
            + "\n\n"
            + LIVE_PROMISE_RE.sub("[Zusage entfernt — kein aktiver Job]", t)
        )
    return t


def assert_live_claim_allowed(job: dict[str, Any] | None) -> None:
    if not may_use_live_language(job=job):
        raise PermissionError("live_claim_without_active_job")
