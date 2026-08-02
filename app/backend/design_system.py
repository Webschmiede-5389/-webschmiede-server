"""Design System routes — local/staging only. No production UI migration."""
from __future__ import annotations

import os
from pathlib import Path

from flask import Blueprint, abort, render_template, request, send_from_directory

_TEMPLATES = Path(__file__).resolve().parent / "templates"
_STATIC_ROOT = Path(__file__).resolve().parents[1] / "static"

design_system_bp = Blueprint(
    "design_system",
    __name__,
    template_folder=str(_TEMPLATES),
)


def design_system_enabled() -> bool:
    """Production defaults to off. local/dev/staging/test allowed."""
    env = (
        os.getenv("APP_ENV")
        or os.getenv("FLASK_ENV")
        or "production"
    ).strip().lower()
    if env in ("production", "prod"):
        return False
    if env in ("local", "development", "dev", "staging", "test"):
        return True
    flag = (os.getenv("DESIGN_SYSTEM_ENABLED") or "").strip().lower()
    return flag in ("1", "true", "yes", "on")


def _env_label() -> str:
    return (
        os.getenv("APP_ENV")
        or os.getenv("FLASK_ENV")
        or "local"
    ).strip().lower()


@design_system_bp.get("/brand/webschmiede/<path:filename>")
def serve_brand_asset(filename: str):
    """Canonical brand files (safe to expose; same class as /ci logos)."""
    return send_from_directory(_STATIC_ROOT / "brand" / "webschmiede", filename)


@design_system_bp.get("/ci/<path:filename>")
def serve_ci_asset(filename: str):
    """Serve CI CSS/assets when Flask runs without Nginx (local/tests)."""
    return send_from_directory(_STATIC_ROOT / "ci", filename)


@design_system_bp.before_request
def _gate_design_system_pages():
    # Static brand/ci assets stay reachable; only HTML lab is gated.
    if request.endpoint in {
        "design_system.serve_brand_asset",
        "design_system.serve_ci_asset",
    }:
        return None
    if not design_system_enabled():
        abort(404)


@design_system_bp.get("/design-system")
def design_system_showcase():
    return render_template(
        "design_system/showcase.html",
        env_label=_env_label(),
        page_title="Design System",
    )


@design_system_bp.get("/design-system/appshell")
def design_system_appshell():
    return render_template(
        "design_system/appshell_proto.html",
        env_label=_env_label(),
        page_title="AppShell Prototyp",
    )
