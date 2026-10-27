"""Fail-closed Creative Designer caller-to-tenant authorization.

Only authenticated server-side identity is trusted. This module does not authenticate.
No agency-wide implicit override and no fallback to request-supplied tenant.
"""
from __future__ import annotations

import hmac
from typing import Any


def authorized_creative_tenant(
    *, session: dict[str, Any] | None, user: dict[str, Any] | None,
    requested_tenant: str | None,
) -> str | None:
    """Return tenant only when authenticated session user owns exactly that tenant.

    Agency staff must use an explicit, separately audited delegation mechanism
    (not implemented here); their role alone does not grant every tenant.
    """
    if not session or not user or not requested_tenant:
        return None
    if session.get("user_id") is None or user.get("id") is None:
        return None
    if str(session["user_id"]) != str(user["id"]):
        return None
    if session.get("kind") != "kunde_admin" or user.get("role") != "kunde_admin":
        return None
    assigned = user.get("kunde_id")
    if not isinstance(assigned, str) or not assigned or assigned == "AGENCY":
        return None
    if not hmac.compare_digest(assigned.encode(), requested_tenant.encode()):
        return None
    return assigned
