"""Creative Designer V1: pure, fail-closed job validation; no dispatch or external writes."""
from __future__ import annotations

import re
from typing import Any

MODES = frozenset({"ORGANIC_SOCIAL", "PAID_PERFORMANCE"})
FORMATS = frozenset({"FEED", "CAROUSEL", "STORY", "REEL"})
TENANT_RE = re.compile(r"^[A-Z][A-Z0-9_-]{1,31}$")
JOB_RE = re.compile(r"^[A-Za-z0-9_-]{6,80}$")


class CreativeJobError(ValueError):
    """Invalid creative job; must not be dispatched."""


def validate_job(payload: dict[str, Any], *, authorized_tenant: str | None) -> dict[str, Any]:
    """Return normalized contract only after independently established tenant identity.

    The caller MUST resolve authorized_tenant from authenticated server-side context,
    never from payload, URL query or X-Tenant-Id. This function is not an auth layer.
    """
    if not isinstance(payload, dict):
        raise CreativeJobError("invalid_payload")
    tenant = payload.get("kunde_id")
    if not isinstance(tenant, str) or not TENANT_RE.fullmatch(tenant) or tenant == "AGENCY":
        raise CreativeJobError("invalid_tenant")
    if not authorized_tenant or authorized_tenant != tenant:
        raise CreativeJobError("tenant_not_authorized")
    mode = payload.get("content_mode")
    if mode not in MODES:
        raise CreativeJobError("invalid_content_mode")
    job_id = payload.get("job_id")
    if not isinstance(job_id, str) or not JOB_RE.fullmatch(job_id):
        raise CreativeJobError("invalid_job_id")
    brief = payload.get("briefing")
    if not isinstance(brief, str) or not brief.strip() or len(brief) > 10000:
        raise CreativeJobError("invalid_briefing")
    formats = payload.get("formats")
    if not isinstance(formats, list) or not formats or any(f not in FORMATS for f in formats):
        raise CreativeJobError("invalid_formats")
    if len(formats) != len(set(formats)):
        raise CreativeJobError("duplicate_formats")
    if mode == "PAID_PERFORMANCE":
        for field in ("conversion_event", "offer", "landing_page", "target_kpi"):
            if not isinstance(payload.get(field), str) or not payload[field].strip():
                raise CreativeJobError("missing_" + field)
    else:
        for field in ("content_pillar", "editorial_goal"):
            if not isinstance(payload.get(field), str) or not payload[field].strip():
                raise CreativeJobError("missing_" + field)
    if payload.get("publish") or payload.get("launch_ads"):
        raise CreativeJobError("publishing_not_allowed")
    return {
        "kunde_id": tenant,
        "job_id": job_id,
        "content_mode": mode,
        "formats": list(formats),
        "briefing": brief.strip(),
        "status": "VALIDATED_NOT_DISPATCHED",
    }
