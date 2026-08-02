# -*- coding: utf-8 -*-
"""Nils persistent job runtime — statuses and validated transitions."""
from __future__ import annotations

from typing import FrozenSet

# Spec statuses + legacy aliases (SUCCEEDED/TIMED_OUT/WAITING/STALLED/…)
STATUSES: FrozenSet[str] = frozenset(
    {
        "RECEIVED",
        "NEEDS_CLARIFICATION",
        "PREFLIGHT",
        "WAITING_FOR_APPROVAL",
        "QUEUED",
        "RUNNING",
        "CANCEL_REQUESTED",
        "CANCELLED",
        "COMPLETED",
        "FAILED",
        "TIMEOUT",
        "RECOVERY_REQUIRED",
        # legacy / operational
        "WAITING",
        "SUCCEEDED",
        "TIMED_OUT",
        "STALLED",
        "RESULT_VALIDATION_FAILED",
    }
)

TERMINAL: FrozenSet[str] = frozenset(
    {
        "COMPLETED",
        "SUCCEEDED",
        "FAILED",
        "TIMEOUT",
        "TIMED_OUT",
        "CANCELLED",
        "RESULT_VALIDATION_FAILED",
    }
)

ACTIVE: FrozenSet[str] = frozenset(
    {
        "RECEIVED",
        "NEEDS_CLARIFICATION",
        "PREFLIGHT",
        "WAITING_FOR_APPROVAL",
        "QUEUED",
        "RUNNING",
        "CANCEL_REQUESTED",
        "WAITING",
        "STALLED",
        "RECOVERY_REQUIRED",
    }
)

# Statuses that may still hold a worker/tool — cancel must interrupt them
CANCELLABLE: FrozenSet[str] = frozenset(
    {
        "RECEIVED",
        "NEEDS_CLARIFICATION",
        "PREFLIGHT",
        "WAITING_FOR_APPROVAL",
        "QUEUED",
        "RUNNING",
        "WAITING",
        "STALLED",
        "CANCEL_REQUESTED",
        "RECOVERY_REQUIRED",
    }
)

# Live-Zusagen nur ab diesen Statuswerten erlaubt
LIVE_CLAIM_OK: FrozenSet[str] = frozenset({"QUEUED", "RUNNING"})

PIPELINE_STAGES: tuple[str, ...] = (
    "INTENT_CHECK",
    "PROJECT_RESOLUTION",
    "INPUT_VALIDATION",
    "CAPABILITY_PREFLIGHT",
    "APPROVAL_CHECK",
    "JOB_CREATION",
    "EXECUTION",
    "RESULT_VALIDATION",
    "MEMORY_EVENT",
    "FINAL_RESPONSE",
)

TRANSITIONS: dict[str, FrozenSet[str]] = {
    "RECEIVED": frozenset(
        {
            "NEEDS_CLARIFICATION",
            "PREFLIGHT",
            "WAITING_FOR_APPROVAL",
            "QUEUED",
            "CANCELLED",
            "CANCEL_REQUESTED",
            "FAILED",
            # Inline read-only completion (CRM offer etc. — never blocks worker queue)
            "SUCCEEDED",
            "COMPLETED",
        }
    ),
    "NEEDS_CLARIFICATION": frozenset(
        {
            "RECEIVED",
            "PREFLIGHT",
            "WAITING_FOR_APPROVAL",
            "CANCELLED",
            "CANCEL_REQUESTED",
            "FAILED",
            # Inline read after parameter fill
            "SUCCEEDED",
            "COMPLETED",
        }
    ),
    "PREFLIGHT": frozenset(
        {
            "WAITING_FOR_APPROVAL",
            "QUEUED",
            "NEEDS_CLARIFICATION",
            "FAILED",
            "CANCELLED",
            "CANCEL_REQUESTED",
            # Inline read-only completion
            "SUCCEEDED",
            "COMPLETED",
        }
    ),
    "WAITING_FOR_APPROVAL": frozenset(
        {
            "QUEUED",
            "PREFLIGHT",
            "CANCELLED",
            "CANCEL_REQUESTED",
            "FAILED",
            # Inline write after explicit approval (e.g. prospect create)
            "SUCCEEDED",
            "COMPLETED",
        }
    ),
    "QUEUED": frozenset({"RUNNING", "CANCELLED", "CANCEL_REQUESTED", "FAILED"}),
    "RUNNING": frozenset(
        {
            "WAITING",
            "WAITING_FOR_APPROVAL",
            "COMPLETED",
            "SUCCEEDED",
            "FAILED",
            "TIMEOUT",
            "TIMED_OUT",
            "STALLED",
            "CANCELLED",
            "CANCEL_REQUESTED",
            "RESULT_VALIDATION_FAILED",
            "RECOVERY_REQUIRED",
        }
    ),
    "WAITING": frozenset(
        {
            "RUNNING",
            "WAITING_FOR_APPROVAL",
            "FAILED",
            "TIMEOUT",
            "TIMED_OUT",
            "STALLED",
            "CANCELLED",
            "CANCEL_REQUESTED",
            "RESULT_VALIDATION_FAILED",
        }
    ),
    "STALLED": frozenset(
        {
            "QUEUED",
            "FAILED",
            "CANCELLED",
            "CANCEL_REQUESTED",
            "RECOVERY_REQUIRED",
        }
    ),
    "CANCEL_REQUESTED": frozenset({"CANCELLED", "FAILED", "STALLED", "RECOVERY_REQUIRED"}),
    "COMPLETED": frozenset(),
    "SUCCEEDED": frozenset(),
    "FAILED": frozenset({"QUEUED", "RECOVERY_REQUIRED"}),
    "TIMEOUT": frozenset({"QUEUED", "CANCELLED", "RECOVERY_REQUIRED"}),
    "TIMED_OUT": frozenset({"QUEUED", "CANCELLED", "RECOVERY_REQUIRED"}),
    "CANCELLED": frozenset(),
    "RESULT_VALIDATION_FAILED": frozenset({"QUEUED", "RECOVERY_REQUIRED"}),
    "RECOVERY_REQUIRED": frozenset(
        {
            "QUEUED",
            "CANCELLED",
            "CANCEL_REQUESTED",
            "FAILED",
            "COMPLETED",
        }
    ),
}


def normalize_status(status: str) -> str:
    """Map legacy aliases to preferred names where useful for display."""
    aliases = {
        "SUCCEEDED": "COMPLETED",
        "TIMED_OUT": "TIMEOUT",
        "WAITING": "WAITING_FOR_APPROVAL",
    }
    return aliases.get(status, status)


def can_transition(from_status: str, to_status: str) -> bool:
    if from_status not in STATUSES or to_status not in STATUSES:
        return False
    if from_status == to_status:
        return True
    return to_status in TRANSITIONS.get(from_status, frozenset())


def assert_transition(from_status: str, to_status: str) -> None:
    if not can_transition(from_status, to_status):
        raise ValueError(f"invalid_status_transition:{from_status}->{to_status}")


def is_active(status: str) -> bool:
    return status in ACTIVE


def is_terminal(status: str) -> bool:
    return status in TERMINAL


def may_claim_live(status: str | None) -> bool:
    return bool(status) and status in LIVE_CLAIM_OK
