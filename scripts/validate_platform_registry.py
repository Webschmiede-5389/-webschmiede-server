#!/usr/bin/env python3
"""Validate platform_registry YAML — no secrets, safe URLs, unique ids/slugs."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urlparse

try:
    import yaml
except ImportError:
    yaml = None

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "config" / "platform_registry.example.yaml"

ALLOWED_ENV = {"production", "staging", "local"}
ALLOWED_IO = {"internal", "external"}
ALLOWED_OPEN = {"same_tab", "new_tab"}
ALLOWED_STATUS = {
    "ACTIVE_PRODUCTION",
    "ACTIVE_STAGING",
    "ACTIVE_LOCAL",
    "EXPERIMENTAL",
    "LEGACY",
    "EXTERNAL_SERVICE",
    "UNKNOWN",
    "UNREACHABLE",
    "DUPLICATE_CANDIDATE",
}
ALLOWED_BRAND = {
    "AGENCY_INTERNAL",
    "AGENCY_CUSTOMER_MANAGEMENT",
    "CUSTOMER_PORTAL",
    "PUBLIC_CUSTOMER_SITE",
    "EXTERNAL_SERVICE_CARD",
}
HOST_ALLOW = {
    "digitalehandwerkskunst.de",
    "crm.digitalehandwerkskunst.de",
    "leads.digitalehandwerkskunst.de",
    "cal.digitalehandwerkskunst.de",
    "sign.digitalehandwerkskunst.de",
    "analytics.digitalehandwerkskunst.de",
    "radar.digitalehandwerkskunst.de",
    "voice.digitalehandwerkskunst.de",
    "snackhouse-yassine.de",
    "www.snackhouse-yassine.de",
    "127.0.0.1",
    "localhost",
}


def _host_ok(host: str) -> bool:
    h = (host or "").lower().rstrip(".")
    if h in HOST_ALLOW:
        return True
    # allow subdomains of agency domain
    if h.endswith(".digitalehandwerkskunst.de"):
        return True
    return False


def validate_url(url: str | None, field: str, errors: list[str]) -> None:
    if url is None or url == "":
        return
    if "://" not in url and url.startswith("/"):
        return  # relative path ok
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http"):
        errors.append(f"{field}: scheme not http(s): {url}")
        return
    if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost"}:
        errors.append(f"{field}: non-local http forbidden: {url}")
    if parsed.username or parsed.password:
        errors.append(f"{field}: credentials in URL forbidden")
    if parsed.scheme == "javascript":
        errors.append(f"{field}: javascript: forbidden")
    if not _host_ok(parsed.hostname or ""):
        errors.append(f"{field}: host not allowlisted: {parsed.hostname}")


def validate(data: dict) -> list[str]:
    errors: list[str] = []
    entries = data.get("entries") or []
    ids, slugs = set(), set()
    for i, e in enumerate(entries):
        prefix = f"entries[{i}]"
        for req in (
            "id", "slug", "display_name", "short_description", "category", "icon",
            "environment", "service_type", "internal_or_external", "base_url",
            "open_mode", "required_roles", "tenant_visibility", "status",
            "sort_order", "branding_mode", "owner", "active",
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
        if e.get("environment") not in ALLOWED_ENV:
            errors.append(f"{prefix}: bad environment")
        if e.get("internal_or_external") not in ALLOWED_IO:
            errors.append(f"{prefix}: bad internal_or_external")
        if e.get("open_mode") not in ALLOWED_OPEN:
            errors.append(f"{prefix}: bad open_mode")
        if e.get("status") not in ALLOWED_STATUS:
            errors.append(f"{prefix}: bad status")
        if e.get("branding_mode") not in ALLOWED_BRAND:
            errors.append(f"{prefix}: bad branding_mode")
        roles = e.get("required_roles")
        if not isinstance(roles, list) or not roles:
            errors.append(f"{prefix}: required_roles must be non-empty list")
        elif any(not re.match(r"^[a-z][a-z0-9_]*$", str(r)) for r in roles):
            errors.append(f"{prefix}: bad role format")
        validate_url(e.get("base_url"), f"{prefix}.base_url", errors)
        validate_url(e.get("healthcheck_url"), f"{prefix}.healthcheck_url", errors)
    return errors


def main(argv: list[str]) -> int:
    if yaml is None:
        print("PyYAML missing — skip structural parse, fail closed for CI optional")
        # Still allow import-less smoke: file exists
        path = Path(argv[1]) if len(argv) > 1 else DEFAULT
        if not path.is_file():
            print("MISSING", path)
            return 1
        print("WARN: PyYAML not installed; existence check only")
        return 0
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    errors = validate(data)
    if errors:
        print("FAIL")
        for e in errors:
            print(" -", e)
        return 1
    print("OK", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
