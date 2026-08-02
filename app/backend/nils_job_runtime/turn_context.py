# -*- coding: utf-8 -*-
"""Multi-turn Telegram job context (parameters + waiting state)."""
from __future__ import annotations

import json
from typing import Any

from nils_job_runtime import store

INTENT_CRM_GET_OFFER = "CRM_GET_OFFER"
INTENT_CRM_OFFER_PDF = "CRM_OFFER_PDF_SEND"
INTENT_CRM_CUSTOMER_READ = "CRM_CUSTOMER_READ"
INTENT_CRM_PROSPECT_CREATE = "CRM_PROSPECT_CREATE"
INTENT_CRM_EMAIL_SEND = "CRM_EMAIL_SEND"
INTENT_CRM_PIPELINE_READ = "CRM_PIPELINE_READ"
INTENT_CRM_LEAD_THREAD = "CRM_LEAD_THREAD"
INTENT_CRM_NOTE_CREATE = "CRM_NOTE_CREATE"
INTENT_CRM_DEAL_STAGE = "CRM_DEAL_STAGE"
INTENT_CRM_DEAL_OPEN = "CRM_DEAL_OPEN"
INTENT_CRM_OFFER_WRITE = "CRM_OFFER_WRITE"
INTENT_CRM_DEAL_CLOSE = "CRM_DEAL_CLOSE"
INTENT_CRM_INBOUND_READ = "CRM_INBOUND_READ"
INTENT_CRM_INBOUND_ACCEPT = "CRM_INBOUND_ACCEPT"
INTENT_DRIVE = "DRIVE"

STATE_WAITING_FOR_INPUT = "WAITING_FOR_INPUT"
STATE_READY_TO_EXECUTE = "READY_TO_EXECUTE"
STATE_AWAITING_CUSTOMER_CHOICE = "AWAITING_CUSTOMER_CHOICE"
STATE_AWAITING_OFFER_CHOICE = "AWAITING_OFFER_CHOICE"
STATE_AWAITING_PROSPECT_APPROVAL = "AWAITING_PROSPECT_APPROVAL"
STATE_AWAITING_EMAIL_APPROVAL = "AWAITING_EMAIL_APPROVAL"
STATE_AWAITING_SALES_APPROVAL = "AWAITING_SALES_APPROVAL"
STATE_AWAITING_ENTITY_KIND = "AWAITING_ENTITY_KIND"
STATE_DONE = "DONE"
STATE_FAILED = "FAILED"

SALES_FIELD_INTENTS = frozenset(
    {
        INTENT_CRM_PIPELINE_READ,
        INTENT_CRM_LEAD_THREAD,
        INTENT_CRM_NOTE_CREATE,
        INTENT_CRM_DEAL_STAGE,
        INTENT_CRM_DEAL_OPEN,
        INTENT_CRM_OFFER_WRITE,
        INTENT_CRM_DEAL_CLOSE,
    }
)


def empty_context(
    *,
    chat_id: str,
    user_id: str | None,
    intent: str,
    missing: list[str] | None = None,
    collected: dict[str, Any] | None = None,
    state: str = STATE_WAITING_FOR_INPUT,
) -> dict[str, Any]:
    now = store.utc_now()
    return {
        "chat_id": str(chat_id),
        "user_id": str(user_id) if user_id else None,
        "intent": intent,
        "collected_parameters": dict(collected or {}),
        "missing_parameters": list(missing or []),
        "state": state,
        "created_at": now,
        "updated_at": now,
        "candidates": {},
    }


def load(job: dict[str, Any] | None) -> dict[str, Any] | None:
    if not job:
        return None
    raw = job.get("turn_context")
    if not raw:
        return None
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def save(job_id: str, ctx: dict[str, Any]) -> dict[str, Any]:
    ctx = dict(ctx)
    ctx["updated_at"] = store.utc_now()
    if "created_at" not in ctx:
        ctx["created_at"] = ctx["updated_at"]
    return store.update_fields(job_id, turn_context=json.dumps(ctx, ensure_ascii=False))


def is_waiting(job: dict[str, Any] | None) -> bool:
    if not job or job.get("status") != "NEEDS_CLARIFICATION":
        return False
    tc = load(job)
    if not tc:
        return False
    return bool(tc.get("missing_parameters")) or tc.get("state") in (
        STATE_WAITING_FOR_INPUT,
        STATE_AWAITING_CUSTOMER_CHOICE,
        STATE_AWAITING_OFFER_CHOICE,
        STATE_AWAITING_ENTITY_KIND,
    )
