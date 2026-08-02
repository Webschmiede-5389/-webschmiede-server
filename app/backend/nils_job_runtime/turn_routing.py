# -*- coding: utf-8 -*-
"""Current-turn-first routing guards for Nils Telegram CRM path.

CURRENT_USER_MESSAGE wins over previous intent/entity/job context unless the
message contains an explicit back-reference.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("nils_job_runtime.turn_routing")

# Explicit anaphora / continuation cues — only then may prior entity be reused.
# Note: bare „das Angebot“ alone is NOT enough (that starts a new offer_read).
_BACKREF_RE = re.compile(
    r"(?i)(?:"
    r"\bnoch\s+einmal\b|\bnochmal\b|\berneut\b|"
    r"\b(?:das\s+angebot|die\s+firma|dieses\s+unternehmen|dieses\s+dokument)"
    r"\s+noch(?:mal|\s+einmal)\b|"
    r"\bnoch(?:mal|\s+einmal)\s+(?:das\s+angebot|die\s+firma)\b|"
    r"\bschick\s+es\b|\bsende\s+es\b|\bzeig\s+es\b|\bhole\s+es\b|\bhol\s+es\b|"
    r"\bschick\s+mir\s+das\b|\bsende\s+mir\s+das\b|"
    r"\blege\s+(?:ihn|sie|den|die)\s+an\b|"
    r"\bdenselben\b|\bdieselbe\b|\bdavon\b|\bdazu\b|"
    r"\bdiese(?:s|r|n)?\s+(?:firma|unternehmen|kunde)\b"
    r")"
)

_CREATE_LEXICAL_RE = re.compile(
    r"(?i)\b("
    r"lege\b|anlegen|erstellen|"
    r"potentiell\w*\s+kunde|interessent|prospect|"
    r"ansprechpartner|als\s+kunde"
    r")\b"
)

_OFFER_LEXICAL_RE = re.compile(
    r"(?i)\b("
    r"angebot|pdf|dokument\s+(?:zeigen|holen|laden|schick)|"
    r"zeig\w*\s+(?:mir\s+)?(?:das\s+)?angebot|"
    r"schick\w*\s+(?:mir\s+)?(?:das\s+)?angebot"
    r")\b"
)

_OFFER_CAPS = frozenset(
    {
        "crm.offer_read",
        "crm.read",
        "crm.offer_pdf_send",
        "crm.offer_write",
    }
)
_CREATE_CAPS = frozenset(
    {
        "crm.prospect_create",
        "crm.customer_write",
        "crm.deal_open",
    }
)
_CREATE_OK_CAPS = frozenset(
    {
        "crm.prospect_create",
        "crm.customer_write",  # may map; preflight blocks write of real customer
    }
)

_FIRM_TOKEN_RE = re.compile(
    r"(?i)\b("
    r"gmbh|ug|ag|kg|ohg|gbr|ltd|inc|llc|firma|unternehmen|company|"
    r"e\.?\s*k\.?|e\.?\s*kfr\.?"
    r")\b"
)

_PERSON_HINT_RE = re.compile(
    r"(?i)\b(person|ansprechpartner|kontakt|natürliche\s+person|natuerliche\s+person)\b"
)
_COMPANY_HINT_RE = re.compile(
    r"(?i)\b(unternehmen|firma|firma\s+anlegen|als\s+unternehmen|firma\s+mit)\b"
)

# „Lege Hassan Yassine …“ / Title-Case names in create phrasing
_NAMED_ENTITY_RE = re.compile(
    r"(?i)(?:^|\blege?\s+|als\s+ansprechpartner\s+bei\s+|bei\s+|von\s+|für\s+|fuer\s+)"
    r"([A-ZÄÖÜ][\w\-]+(?:\s+[A-ZÄÖÜ][\w\-]+){0,5})"
)


@dataclass
class GuardResult:
    ok: bool
    reason: str = ""
    action: str = "allow"  # allow | block | cancel_and_repipe | clarify
    context_reused: bool = False
    reuse_reason: str = ""
    current_intent: str = ""
    previous_intent: str = ""
    current_entity: str = ""
    previous_entity: str = ""
    selected_capability: str = ""
    selected_tool: str = ""
    final_action: str = ""
    extras: dict[str, Any] = field(default_factory=dict)


def has_backreference(text: str) -> bool:
    return bool(_BACKREF_RE.search(text or ""))


def has_create_lexical(text: str) -> bool:
    return bool(_CREATE_LEXICAL_RE.search(text or ""))


def has_offer_lexical(text: str) -> bool:
    return bool(_OFFER_LEXICAL_RE.search(text or ""))


def looks_like_company_name(name: str) -> bool:
    n = (name or "").strip()
    if not n:
        return False
    if _FIRM_TOKEN_RE.search(n):
        return True
    # Single token with GmbH-like casing already handled; long ALLCAPS acronyms
    if re.search(r"(?i)\b(service|handwerk|gastro|dach|bau|consult)\b", n):
        return True
    return False


def looks_like_person_name(name: str) -> bool:
    n = (name or "").strip()
    if not n or looks_like_company_name(n):
        return False
    parts = [p for p in re.split(r"\s+", n) if p]
    if len(parts) < 2 or len(parts) > 4:
        return False
    # First+Last style (allow lowercase particles like von/de)
    good = 0
    for p in parts:
        if re.match(r"(?i)^(von|van|de|del|di|da|la|le)$", p):
            continue
        if re.match(r"^[A-ZÄÖÜ][\w\-]+$", p):
            good += 1
        else:
            return False
    return good >= 2


def extract_named_entities(text: str) -> list[str]:
    """Best-effort named entities from the current user message only."""
    t = (text or "").strip()
    if not t:
        return []
    found: list[str] = []
    # Prefer structured create patterns
    patterns = (
        r"(?i)^\s*lege?\s+(.+?)\s+als\s+(?:ansprechpartner|kontakt)\s+(?:bei|von)\s+(.+?)\s+an\s*$",
        r"(?i)^\s*lege?\s+(.+?)\s+als\s+(?:einen?\s+|ein\s+)?"
        r"(?:interessenten?|prospect|potentiell\w*\s+kunden?)\s+an\s*$",
        r"(?i)^\s*lege?\s+(.+?)\s+mit\s+(.+?)\s+an\s*$",
        r"(?i)^\s*lege?\s+(?:die\s+|das\s+|den\s+)?(?:firma|unternehmen)\s+(.+?)\s+an\s*$",
        r"(?i)^\s*lege?\s+(.+?)\s+an\s*$",
        r"(?i)angebot\s+(?:von|für|fuer)\s+(.+?)\s*$",
    )
    for pat in patterns:
        m = re.search(pat, t)
        if not m:
            continue
        for g in m.groups():
            name = (g or "").strip().strip(" .!?\"'")
            name = re.sub(
                r"(?i)^(einen?|ein|die|das|den|firma|unternehmen)\s+",
                "",
                name,
            ).strip()
            if name and len(name) >= 2 and name.lower() not in (
                "interessenten",
                "interessent",
                "prospect",
                "kunden",
                "kunde",
            ):
                if name not in found:
                    found.append(name[:120])
        if found:
            return found
    for m in _NAMED_ENTITY_RE.finditer(t):
        name = (m.group(1) or "").strip().strip(" .!?\"'")
        if name and name not in found and len(name) >= 3:
            found.append(name[:120])
    return found


def primary_entity(text: str) -> str:
    ents = extract_named_entities(text)
    return ents[0] if ents else ""


def previous_entity_from_turn(turn: dict[str, Any] | None) -> str:
    if not turn:
        return ""
    collected = turn.get("collected_parameters") or {}
    for key in ("company", "customer", "contact"):
        val = (collected.get(key) or "").strip()
        if val:
            return val[:120]
    return ""


def previous_intent_from_turn(turn: dict[str, Any] | None) -> str:
    if not turn:
        return ""
    return str(turn.get("intent") or "")


def entities_conflict(current: str, previous: str) -> bool:
    cur = (current or "").strip().lower()
    prev = (previous or "").strip().lower()
    if not cur or not prev:
        return False
    if cur == prev:
        return False
    # Substring match (MBP vs mbp Service GmbH) → same family, not a leak conflict
    if cur in prev or prev in cur:
        return False
    # Token overlap (≥2 shared significant tokens) → likely same
    cur_tok = {t for t in re.split(r"\W+", cur) if len(t) > 2}
    prev_tok = {t for t in re.split(r"\W+", prev) if len(t) > 2}
    if cur_tok and prev_tok and len(cur_tok & prev_tok) >= 2:
        return False
    return True


def validate_intent_consistency(text: str, capability: str) -> GuardResult:
    """Lexical intent must match selected capability class."""
    cap = (capability or "").strip()
    t = text or ""
    create_lex = has_create_lexical(t)
    offer_lex = has_offer_lexical(t)

    if create_lex and not offer_lex and cap in _OFFER_CAPS:
        return GuardResult(
            ok=False,
            reason="create_lexical_vs_offer_capability",
            action="block",
            current_intent="CREATE_PROSPECT",
            selected_capability=cap,
            final_action="block_tool",
        )
    if offer_lex and not create_lex and cap in _CREATE_CAPS:
        # Offer language with create cap is unusual — only block if strong offer cue
        if re.search(r"(?i)\bangebot\b", t) and not re.search(
            r"(?i)\b(?:anlegen|erstellen|lege)\b", t
        ):
            return GuardResult(
                ok=False,
                reason="offer_lexical_vs_create_capability",
                action="block",
                current_intent="GET_OFFER",
                selected_capability=cap,
                final_action="block_tool",
            )
    if create_lex and cap and cap not in _CREATE_OK_CAPS | {
        "crm.note_create",
        "crm.deal_open",
        "crm.inbound_accept",
        "drive.doc_create",
        "drive.sheet_create",
        "calendar.create",
    }:
        # Soft: create wording but unrelated cap — block offer tools only (above)
        pass
    return GuardResult(ok=True, reason="intent_consistent", selected_capability=cap)


def validate_entity_against_message(
    text: str,
    entity: str,
    *,
    allow_backref: bool = True,
) -> GuardResult:
    """Main entity must appear in current message unless backref allows prior."""
    ent = (entity or "").strip()
    if not ent:
        return GuardResult(ok=True, reason="no_entity")
    t = (text or "").lower()
    ent_l = ent.lower()
    if ent_l in t:
        return GuardResult(ok=True, reason="entity_in_message", current_entity=ent)
    # Token presence (≥2 tokens)
    tokens = [tok for tok in re.split(r"\W+", ent_l) if len(tok) > 2]
    if tokens and sum(1 for tok in tokens if tok in t) >= min(2, len(tokens)):
        return GuardResult(ok=True, reason="entity_tokens_in_message", current_entity=ent)
    if allow_backref and has_backreference(text):
        return GuardResult(
            ok=True,
            reason="backref_allows_prior_entity",
            context_reused=True,
            reuse_reason="explicit_backreference",
            current_entity=ent,
        )
    return GuardResult(
        ok=False,
        reason="entity_not_in_message_no_backref",
        action="block",
        current_entity=ent,
        final_action="block_stale_entity",
    )


def validate_tool_vs_intent(capability: str, tool: str) -> GuardResult:
    cap = (capability or "").strip()
    tool_l = (tool or "").strip().lower()
    if not tool_l:
        return GuardResult(ok=True, reason="no_tool")
    if cap in _CREATE_CAPS and any(
        x in tool_l for x in ("offer_read", "get_offer", "offer_pdf", "fetch_document")
    ):
        return GuardResult(
            ok=False,
            reason="create_intent_vs_offer_tool",
            action="block",
            selected_capability=cap,
            selected_tool=tool_l,
            final_action="block_tool",
        )
    if cap in _OFFER_CAPS and any(
        x in tool_l for x in ("prospect_create", "customer_write", "create_prospect")
    ):
        return GuardResult(
            ok=False,
            reason="offer_intent_vs_create_tool",
            action="block",
            selected_capability=cap,
            selected_tool=tool_l,
            final_action="block_tool",
        )
    return GuardResult(ok=True, reason="tool_matches_intent", selected_capability=cap, selected_tool=tool_l)


def should_reuse_prior_entity(
    *,
    text: str,
    current_entity: str,
    previous_entity: str,
) -> GuardResult:
    """Current-turn-first: reuse prior entity only with backref and no conflict."""
    if not previous_entity:
        return GuardResult(ok=True, context_reused=False, reuse_reason="no_previous")
    if current_entity and entities_conflict(current_entity, previous_entity):
        return GuardResult(
            ok=False,
            reason="named_entity_overrides_previous",
            action="cancel_and_repipe",
            context_reused=False,
            reuse_reason="conflict_new_named_entity",
            current_entity=current_entity,
            previous_entity=previous_entity,
            final_action="drop_previous_entity",
        )
    if has_backreference(text) and not current_entity:
        return GuardResult(
            ok=True,
            context_reused=True,
            reuse_reason="explicit_backreference",
            current_entity=previous_entity,
            previous_entity=previous_entity,
        )
    if current_entity:
        return GuardResult(
            ok=True,
            context_reused=False,
            reuse_reason="current_entity_wins",
            current_entity=current_entity,
            previous_entity=previous_entity,
        )
    # No current entity, no backref → do not silently reuse
    return GuardResult(
        ok=False,
        reason="no_backref_no_current_entity",
        action="block",
        context_reused=False,
        reuse_reason="blocked_silent_reuse",
        previous_entity=previous_entity,
        final_action="require_explicit_entity_or_backref",
    )


def is_entity_kind_clarification_reply(text: str) -> bool:
    """True for answers to person/company clarify (not a brand-new create command)."""
    t = (text or "").strip()
    if not t:
        return False
    if re.search(
        r"(?i)(?:als\s+)?(?:ansprechpartner|kontakt)\s+(?:bei|von)\s+\S+",
        t,
    ):
        return True
    if resolve_entity_kind_answer(t):
        return True
    return False


def evaluate_resume_gate(
    *,
    text: str,
    mapped_capability: str | None,
    previous_intent: str,
    previous_entity: str,
    detect_execution: bool,
    missing_parameters: list[str] | None = None,
) -> GuardResult:
    """Decide whether a waiting job may consume this message as parameter fill."""
    cur_ent = primary_entity(text)
    mapped = (mapped_capability or "").strip()
    missing = list(missing_parameters or [])

    # Waiting for entity_kind / company after prospect clarify → allow answer fill
    if missing and missing[0] in ("entity_kind", "company", "customer"):
        if is_entity_kind_clarification_reply(text) or (
            missing[0] in ("company", "customer")
            and cur_ent
            and not mapped
            and not re.search(r"(?i)\b(?:zeig|schick|sende|hole)\w*\b", text or "")
        ):
            return GuardResult(
                ok=True,
                reason="clarification_parameter_fill",
                action="allow",
                context_reused=True,
                reuse_reason="waiting_entity_kind_or_company",
                current_entity=cur_ent or previous_entity,
                previous_entity=previous_entity,
                previous_intent=previous_intent,
                final_action="resume_fill",
            )

    if mapped:
        # New mapped capability always starts a fresh turn (caller cancels wait job)
        return GuardResult(
            ok=False,
            reason="new_mapped_capability",
            action="cancel_and_repipe",
            current_intent=mapped,
            previous_intent=previous_intent,
            current_entity=cur_ent,
            previous_entity=previous_entity,
            selected_capability=mapped,
            final_action="cancel_waiting_job",
        )

    if detect_execution or has_create_lexical(text):
        # Clarification replies often contain „Ansprechpartner“ — not a new job
        if is_entity_kind_clarification_reply(text):
            return GuardResult(
                ok=True,
                reason="clarification_reply_not_new_create",
                action="allow",
                context_reused=True,
                reuse_reason="entity_kind_answer",
                current_entity=cur_ent,
                previous_entity=previous_entity,
                previous_intent=previous_intent,
                final_action="resume_fill",
            )
        # New action phrasing while waiting — do not treat as company fill
        return GuardResult(
            ok=False,
            reason="new_execution_or_create_lexical",
            action="cancel_and_repipe",
            previous_intent=previous_intent,
            current_entity=cur_ent,
            previous_entity=previous_entity,
            final_action="cancel_waiting_job",
        )

    if cur_ent and previous_entity and entities_conflict(cur_ent, previous_entity):
        return GuardResult(
            ok=False,
            reason="entity_leak_on_resume",
            action="cancel_and_repipe",
            current_entity=cur_ent,
            previous_entity=previous_entity,
            previous_intent=previous_intent,
            final_action="cancel_waiting_job",
        )

    if cur_ent and previous_intent in (
        "CRM_GET_OFFER",
        "CRM_OFFER_PDF_SEND",
        "CRM_CUSTOMER_READ",
    ):
        # Named entity without backref while waiting for offer/customer param:
        # only resume if message is a bare name (parameter answer), not a create phrase.
        if has_create_lexical(text):
            return GuardResult(
                ok=False,
                reason="create_lexical_during_offer_wait",
                action="cancel_and_repipe",
                current_entity=cur_ent,
                previous_entity=previous_entity,
                previous_intent=previous_intent,
                final_action="cancel_waiting_job",
            )
        # Bare name / short parameter → allow resume
        if len((text or "").split()) <= 6 and not has_offer_lexical(text):
            return GuardResult(
                ok=True,
                reason="parameter_fill",
                action="allow",
                context_reused=True,
                reuse_reason="waiting_parameter_fill",
                current_entity=cur_ent,
                previous_entity=previous_entity,
                previous_intent=previous_intent,
                final_action="resume_fill",
            )

    return GuardResult(
        ok=True,
        reason="resume_allowed",
        action="allow",
        context_reused=bool(previous_entity and not cur_ent and has_backreference(text)),
        reuse_reason="backref" if has_backreference(text) else "parameter_or_choice",
        current_entity=cur_ent,
        previous_entity=previous_entity,
        previous_intent=previous_intent,
        final_action="resume_fill",
    )


def resolve_entity_kind_answer(text: str) -> str:
    """Return 'person' | 'company' | '' from clarification reply."""
    t = (text or "").strip().lower()
    if _PERSON_HINT_RE.search(t) or t in (
        "person",
        "ansprechpartner",
        "kontakt",
        "mensch",
        "privat",
    ):
        return "person"
    if _COMPANY_HINT_RE.search(t) or t in (
        "unternehmen",
        "firma",
        "company",
        "betrieb",
        "firma anlegen",
    ):
        return "company"
    return ""


def needs_entity_kind_clarification(
    *,
    text: str,
    company_name: str,
    contact_name: str = "",
) -> bool:
    """True when name is person-like and message does not pin company vs person."""
    if contact_name and company_name and contact_name != company_name:
        return False
    if looks_like_company_name(company_name):
        return False
    if re.search(
        r"(?i)\bals\s+(?:ansprechpartner|kontakt)\s+(?:bei|von)\b",
        text or "",
    ):
        return False
    if re.search(r"(?i)\b(?:firma|unternehmen)\s+", text or ""):
        return False
    return looks_like_person_name(company_name)


def log_turn_routing(
    *,
    chat_id: str | None = None,
    message_id: int | str | None = None,
    job_id: str | None = None,
    current_intent: str = "",
    previous_intent: str = "",
    current_entity: str = "",
    previous_entity: str = "",
    context_reused: bool = False,
    reuse_reason: str = "",
    selected_capability: str = "",
    selected_tool: str = "",
    guard_result: str = "",
    final_action: str = "",
    extra: dict[str, Any] | None = None,
) -> None:
    payload = {
        "chat_id": str(chat_id or "")[:32],
        "message_id": message_id,
        "job_id": job_id,
        "current_intent": current_intent,
        "previous_intent": previous_intent,
        "current_entity": (current_entity or "")[:80],
        "previous_entity": (previous_entity or "")[:80],
        "context_reused": bool(context_reused),
        "reuse_reason": reuse_reason,
        "selected_capability": selected_capability,
        "selected_tool": selected_tool,
        "guard_result": guard_result,
        "final_action": final_action,
    }
    if extra:
        # Avoid dumping full message bodies / secrets
        for k, v in extra.items():
            if k in ("text", "body", "prompt", "history"):
                continue
            payload[k] = v
    log.info("nils_turn_routing %s", payload)
