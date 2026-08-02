"""Agency API: Werkzeuge from platform_registry.yaml (fail-closed)."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from platform_registry import CATEGORY_ORDER, current_app_env, load_filtered

platform_tools_bp = Blueprint("platform_tools", __name__)


def _roles_from_request() -> list[str]:
    """Map agency session to coarse roles. No new auth model / no SSO."""
    roles = ["agency", "agency_admin"]
    env = current_app_env()
    if env in ("local", "development", "dev", "staging", "test"):
        override = (request.headers.get("X-Agency-Tools-Role") or "").strip().lower()
        if override == "agency":
            return ["agency"]
        if override == "agency_admin":
            return ["agency", "agency_admin"]
        if override == "none":
            return []
    return roles


@platform_tools_bp.get("/api/agency/tools")
def agency_tools_list():
    """Auth applied in main.py via require_agency_admin wrap after register."""
    viewer_env = current_app_env()
    entries, errors = load_filtered(roles=_roles_from_request(), viewer_env=viewer_env)
    if errors:
        return jsonify({
            "ok": False,
            "error": "registry_unavailable",
            "details": errors[:20],
            "entries": [],
            "categories": CATEGORY_ORDER,
            "env": viewer_env,
        }), 503
    safe = []
    for e in entries:
        safe.append({
            "id": e.get("id"),
            "slug": e.get("slug"),
            "display_name": e.get("display_name"),
            "short_description": e.get("short_description"),
            "category": e.get("category"),
            "icon": e.get("icon"),
            "environment": e.get("environment"),
            "internal_or_external": e.get("internal_or_external"),
            "base_url": e.get("base_url"),
            "open_mode": e.get("open_mode"),
            "status": e.get("status"),
            "sort_order": e.get("sort_order"),
            "branding_mode": e.get("branding_mode"),
            "owner": e.get("owner"),
        })
    return jsonify({
        "ok": True,
        "entries": safe,
        "categories": CATEGORY_ORDER,
        "env": viewer_env,
        "count": len(safe),
    })
