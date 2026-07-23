"""Kunden-ID Schema — Branchen-Prefix, Vergabe, Validierung."""
from __future__ import annotations

import re
from pathlib import Path

# Branche (slug) → 3-Buchstaben-Prefix
BRANCHE_PREFIX: dict[str, str] = {
    "restaurant": "SHY",
    "gastro": "SHY",
    "imbiss": "SHY",
    "pizzeria": "SHY",
    "handwerk": "HWK",
    "maler": "HWK",
    "dach": "HWK",
    "elektro": "HWK",
    "beauty": "BTY",
    "friseur": "BTY",
    "kosmetik": "BTY",
    "fitness": "FIT",
    "praxis": "MED",
    "arzt": "MED",
    "anwalt": "RCH",
    "kanzlei": "RCH",
    "immobilien": "IMB",
    "sonstiges": "KND",
}

PREFIX_BRANCHE_LABEL: dict[str, str] = {
    "SHY": "Gastro / Restaurant",
    "HWK": "Handwerk",
    "BTY": "Beauty / Friseur",
    "FIT": "Fitness",
    "MED": "Praxis / Medizin",
    "RCH": "Kanzlei / Beratung",
    "IMB": "Immobilien",
    "KND": "Sonstiges",
}

ID_PATTERN = re.compile(r"^([A-Z]{3})(\d{3})$")


def prefix_for_branche(branche: str) -> str:
    key = (branche or "").strip().lower()
    return BRANCHE_PREFIX.get(key, "KND")


def validate_kunde_id(kid: str) -> bool:
    return bool(ID_PATTERN.match((kid or "").strip().upper()))


def parse_kunde_id(kid: str) -> tuple[str, int] | None:
    m = ID_PATTERN.match((kid or "").strip().upper())
    if not m:
        return None
    return m.group(1), int(m.group(2))


def n8n_slug(kid: str) -> str:
    """SHY001 → shy001 (Webhook-Pfad)."""
    return (kid or "").strip().lower()


def n8n_order_webhook(kid: str, base: str = "http://127.0.0.1:5678") -> str:
    return f"{base.rstrip('/')}/webhook/new-order-{n8n_slug(kid)}"


def invoice_number(kid: str, year: int | None = None) -> str:
    from datetime import datetime

    y = year or datetime.now().year
    return f"WS-{y}-{kid.upper()}"


def suggest_next_id(kunden_dir: Path | str, prefix: str = "SHY") -> str:
    prefix = (prefix or "KND").upper()[:3]
    nums: list[int] = []
    root = Path(kunden_dir)
    if root.is_dir():
        for p in root.glob("*.json"):
            m = re.match(rf"^{re.escape(prefix)}(\d{{3}})", p.name.upper())
            if m:
                nums.append(int(m.group(1)))
            else:
                try:
                    import json

                    data = json.loads(p.read_text(encoding="utf-8"))
                    pid = (data.get("id") or "").upper()
                    m2 = re.match(rf"^{re.escape(prefix)}(\d{{3}})$", pid)
                    if m2:
                        nums.append(int(m2.group(1)))
                except Exception:
                    pass
    n = max(nums, default=0) + 1
    return f"{prefix}{n:03d}"


def suggest_next_id_for_branche(kunden_dir: Path | str, branche: str) -> str:
    return suggest_next_id(kunden_dir, prefix_for_branche(branche))


def list_prefixes() -> list[dict[str, str]]:
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for branche, prefix in sorted(BRANCHE_PREFIX.items(), key=lambda x: (x[1], x[0])):
        if prefix in seen:
            continue
        seen.add(prefix)
        out.append({
            "prefix": prefix,
            "label": PREFIX_BRANCHE_LABEL.get(prefix, prefix),
            "beispiel": f"{prefix}001",
        })
    return out
