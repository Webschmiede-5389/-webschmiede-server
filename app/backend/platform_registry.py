"""Load and filter platform_registry.yaml — fail-closed, no secrets in URLs."""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

log = logging.getLogger("platform_registry")

_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_PATH = _ROOT / "config" / "platform_registry.yaml"

ALLOWED_SCHEMES = {"https", "http"}
LOCAL_HOSTS = {"127.0.0.1", "localhost"}
PRIVATE_IP_RE = re.compile(
    r"^(10\.|127\.|192\.168\.|172\.(1[6-9]|2\d|3[0-1])\.|0\.0\.0\.0$|::1$)"
)
ROLE_RE = re.compile(r"^[a-z][a-z0-9_]*$")

# Categories for Werkzeuge UI (display order)
CATEGORY_ORDER = [
    "Zentrale",
    "Vertrieb",
    "Leads",
    "CRM",
    "Kunden",
    "Kommunikation",
    "Content",
    "Automatisierung",
    "Dokumente",
    "Betrieb",
    "Externe Dienste",
    "Entwicklung & Staging",
]


class RegistryError(Exception):
    """Fatal registry load failure (fail-closed)."""


def _host_allowed(host: str | None) -> bool:
    if not host:
        return False
    h = host.lower().rstrip(".")
    if h in LOCAL_HOSTS:
        return True
    if h.endswith(".digitalehandwerkskunst.de") or h == "digitalehandwerkskunst.de":
        return True
    if h.endswith(".snackhouse-yassine.de") or h == "snackhouse-yassine.de":
        return True
    return False


def validate_entry_url(url: str | None, *, production: bool) -> str | None:
    """Return error message or None if OK. Relative /paths allowed."""
    if url is None or url == "":
        return "missing url"
    if url.startswith("javascript:") or url.startswith("data:"):
        return "forbidden scheme"
    if url.startswith("/") and not url.startswith("//"):
        return None
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        return f"bad scheme {parsed.scheme!r}"
    if parsed.username or parsed.password:
        return "credentials in url"
    host = parsed.hostname or ""
    if PRIVATE_IP_RE.match(host) and production:
        return "private ip in production"
    if host in LOCAL_HOSTS and production:
        return "localhost in production"
    if parsed.scheme == "http" and host not in LOCAL_HOSTS:
        return "non-local http"
    if not _host_allowed(host):
        return f"host not allowlisted: {host}"
    # Query credentials heuristics
    q = (parsed.query or "").lower()
    if any(k in q for k in ("token=", "apikey=", "api_key=", "password=", "secret=")):
        return "credential-like query"
    return None


def current_app_env() -> str:
    return (
        os.getenv("APP_ENV")
        or os.getenv("FLASK_ENV")
        or "production"
    ).strip().lower()


def is_production_env(env: str | None = None) -> bool:
    e = (env or current_app_env()).lower()
    return e in ("production", "prod")


def load_raw(path: Path | None = None) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:
        raise RegistryError("PyYAML required for platform registry") from exc

    p = path or _DEFAULT_PATH
    if not p.is_file():
        raise RegistryError(f"registry file missing: {p}")
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RegistryError(f"registry parse failed: {exc}") from exc
    if not isinstance(data, dict) or "entries" not in data:
        raise RegistryError("registry must be a mapping with entries")
    if not isinstance(data["entries"], list):
        raise RegistryError("entries must be a list")
    return data


def validate_registry(data: dict[str, Any], *, production: bool | None = None) -> list[str]:
    """Structural + security validation. Returns list of errors (empty = ok)."""
    prod = is_production_env() if production is None else production
    errors: list[str] = []
    ids: set[str] = set()
    slugs: set[str] = set()
    for i, e in enumerate(data.get("entries") or []):
        if not isinstance(e, dict):
            errors.append(f"entries[{i}]: not a mapping")
            continue
        prefix = f"entries[{i}]"
        for req in (
            "id",
            "slug",
            "display_name",
            "short_description",
            "category",
            "icon",
            "environment",
            "service_type",
            "internal_or_external",
            "base_url",
            "open_mode",
            "required_roles",
            "tenant_visibility",
            "status",
            "sort_order",
            "branding_mode",
            "owner",
            "active",
        ):
            if req not in e:
                errors.append(f"{prefix}: missing {req}")
        eid, slug = e.get("id"), e.get("slug")
        if eid in ids:
            errors.append(f"{prefix}: duplicate id {eid}")
        if slug in slugs:
            errors.append(f"{prefix}: duplicate slug {slug}")
        ids.add(eid)
        slugs.add(slug)
        roles = e.get("required_roles")
        if not isinstance(roles, list) or not roles:
            errors.append(f"{prefix}: required_roles must be non-empty list")
        elif any(not ROLE_RE.match(str(r)) for r in roles):
            errors.append(f"{prefix}: bad role format")
        err = validate_entry_url(e.get("base_url"), production=prod)
        if err:
            errors.append(f"{prefix}.base_url: {err}")
        hc = e.get("healthcheck_url")
        if hc:
            err_hc = validate_entry_url(hc, production=prod)
            if err_hc:
                errors.append(f"{prefix}.healthcheck_url: {err_hc}")
    return errors


def _viewer_env_allows(entry_env: str, viewer_env: str) -> bool:
    """Staging/local tools hidden from production viewers."""
    ve = viewer_env.lower()
    ee = (entry_env or "").lower()
    if ve in ("production", "prod"):
        return ee == "production"
    if ve == "staging":
        return ee in ("production", "staging")
    # local/dev/test: see all active
    return True


def filter_entries(
    entries: list[dict[str, Any]],
    *,
    roles: list[str] | set[str] | None = None,
    viewer_env: str | None = None,
    include_inactive: bool = False,
) -> list[dict[str, Any]]:
    """Safe filter for Werkzeuge UI. Skips invalid cards instead of crashing."""
    role_set = {str(r).lower() for r in (roles or ["agency"])}
    env = (viewer_env or current_app_env()).lower()
    production = is_production_env(env)
    out: list[dict[str, Any]] = []
    for e in entries:
        try:
            if not include_inactive and not e.get("active", True):
                continue
            if not _viewer_env_allows(str(e.get("environment", "")), env):
                continue
            required = {str(r).lower() for r in (e.get("required_roles") or [])}
            effective = set(role_set)
            if "agency_admin" in effective:
                effective.add("agency")
            if required and effective.isdisjoint(required):
                continue
            err = validate_entry_url(e.get("base_url"), production=production)
            if err:
                log.warning("skip tool %s: %s", e.get("id"), err)
                continue
            card = dict(e)
            card["_safe"] = True
            out.append(card)
        except Exception as exc:  # noqa: BLE001 — one bad card must not kill page
            log.warning("skip broken tool card: %s", exc)
            continue
    out.sort(key=lambda x: (int(x.get("sort_order") or 9999), str(x.get("display_name") or "")))
    return out


def load_filtered(
    *,
    roles: list[str] | set[str] | None = None,
    viewer_env: str | None = None,
    path: Path | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Returns (entries, load_errors). On fatal error, entries=[] and errors set."""
    try:
        data = load_raw(path)
        errs = validate_registry(data)
        if errs:
            # Fail-closed for structural issues
            return [], errs
        return filter_entries(data["entries"], roles=roles, viewer_env=viewer_env), []
    except RegistryError as exc:
        return [], [str(exc)]
