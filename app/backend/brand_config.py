"""BrandConfig helpers — validate controlled branding, no free CSS."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")

MODES = {
    "AGENCY_INTERNAL",
    "AGENCY_CUSTOMER_MANAGEMENT",
    "CUSTOMER_PORTAL",
    "PUBLIC_CUSTOMER_SITE",
    "EXTERNAL_SERVICE_CARD",
}

AGENCY_DEFAULTS = {
    "mode": "AGENCY_INTERNAL",
    "brand_name": "WebSchmiede",
    "brand_subtitle": "Digitale Handwerkskunst",
    "logo_full": "/brand/webschmiede/logo-horizontal.png",
    "logo_compact": "/brand/webschmiede/logo-mark.png",
    "favicon": "/brand/webschmiede/favicon.png",
    "primary_color": "#FF6600",
    "primary_hover": "#E55A00",
    "support_name": "Digitale Handwerkskunst",
    "support_url": "https://digitalehandwerkskunst.de/agency-hub",
    "powered_by_visible": False,
}


@dataclass(frozen=True)
class BrandConfig:
    mode: str
    brand_name: str
    brand_subtitle: str
    logo_full: str
    logo_compact: str
    favicon: str
    primary_color: str
    primary_hover: str
    support_name: str
    support_url: str
    powered_by_visible: bool


class BrandConfigError(ValueError):
    pass


def _require_hex(value: str, field: str) -> str:
    if not HEX.match(value or ""):
        raise BrandConfigError(f"{field} must be #RRGGBB")
    return value.upper() if False else value  # keep original case


def _safe_path(value: str, field: str) -> str:
    v = (value or "").strip()
    if not v.startswith("/"):
        raise BrandConfigError(f"{field} must be a root-relative path")
    if ".." in v or "\\" in v or v.lower().startswith("/javascript"):
        raise BrandConfigError(f"{field} unsafe path")
    if any(x in v.lower() for x in ("<", ">", '"', "'", " ")):
        raise BrandConfigError(f"{field} invalid characters")
    return v


def validate_brand_dict(data: dict[str, Any]) -> BrandConfig:
    if not isinstance(data, dict):
        raise BrandConfigError("brand config must be object")
    # Reject free CSS/JS injection attempts
    for banned in ("custom_css", "custom_js", "css", "javascript", "style_block"):
        if banned in data and data[banned]:
            raise BrandConfigError(f"{banned} not allowed")
    mode = data.get("mode") or "AGENCY_INTERNAL"
    if mode not in MODES:
        raise BrandConfigError(f"unknown mode {mode}")
    base = dict(AGENCY_DEFAULTS)
    base.update({k: v for k, v in data.items() if v is not None})
    base["mode"] = mode
    return BrandConfig(
        mode=mode,
        brand_name=str(base["brand_name"])[:80],
        brand_subtitle=str(base["brand_subtitle"])[:120],
        logo_full=_safe_path(str(base["logo_full"]), "logo_full"),
        logo_compact=_safe_path(str(base["logo_compact"]), "logo_compact"),
        favicon=_safe_path(str(base["favicon"]), "favicon"),
        primary_color=_require_hex(str(base["primary_color"]), "primary_color"),
        primary_hover=_require_hex(str(base["primary_hover"]), "primary_hover"),
        support_name=str(base.get("support_name") or "")[:80],
        support_url=str(base.get("support_url") or "")[:200],
        powered_by_visible=bool(base.get("powered_by_visible")),
    )


def agency_internal() -> BrandConfig:
    return validate_brand_dict(dict(AGENCY_DEFAULTS))
