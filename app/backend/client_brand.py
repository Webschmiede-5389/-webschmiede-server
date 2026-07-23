"""Kunden-CI / Brand für Onboarding, Tischaufsteller, Druckvorlagen."""
from __future__ import annotations

GASTRO_BRANCHEN = frozenset({"restaurant", "gastro", "imbiss", "cafe", "bar"})


def is_gastro(branche: str | None) -> bool:
    return (branche or "").strip().lower() in GASTRO_BRANCHEN


def default_gastro_brand(*, slug: str, name: str = "") -> dict:
    """Standard-CI für neue Gastronomen (Dunkel + Gold). Logo unter /brand/{slug}-logo.png hinterlegen."""
    logo = f"/brand/{slug}-logo.png" if slug else "/brand/logo.png"
    return {
        "logo": logo,
        "logo_shape": "diamond",
        "colors": {
            "gold": "#C9A84C",
            "gold_soft": "#F0D878",
            "dark": "#0e0b08",
            "ink": "#f5f0e8",
            "muted": "#a39888",
            "border": "#3a3228",
        },
        "font_display": "Playfair Display",
        "font_body": "Inter",
        "table": {
            "tag": "Am Tisch",
            "headline": "Hier bestellen",
            "sub": "Code scannen, am Handy bestellen. Wir bringen es euch.",
            "promo": "Erste Online-Bestellung: 5 % Rabatt",
            "hint": "Keine Lust aufs Handy? Einfach an der Theke bestellen.",
        },
        "google": {
            "tag": "An der Theke",
            "headline": "Hat’s geschmeckt?",
            "sub": "Kurz bewerten. Hilft uns enorm und dauert nur einen Moment.",
            "promo": "Google-Bewertung",
            "hint": "Für Gäste an der Theke oder nach dem Essen.",
        },
    }


def resolve_brand(k: dict) -> dict:
    """Kunden-brand mit Gastro-Defaults mergen."""
    slug = (k.get("slug") or "").strip()
    name = (k.get("name") or "").strip()
    base = default_gastro_brand(slug=slug or "kunde", name=name) if is_gastro(k.get("branche")) else {
        "logo": f"/brand/{slug}-logo.png" if slug else "",
        "logo_shape": "square",
        "colors": {
            "gold": "#FF6600",
            "gold_soft": "#FFF4ED",
            "dark": "#1A1A1A",
            "ink": "#FFFFFF",
            "muted": "#888888",
            "border": "#333333",
        },
        "font_display": "Inter",
        "font_body": "Inter",
        "table": {},
        "google": {},
    }
    raw = k.get("brand") or {}
    out = dict(base)
    out.update({k_: v for k_, v in raw.items() if k_ not in ("colors", "table", "google") and v not in (None, "")})
    colors = dict(base.get("colors") or {})
    colors.update((raw.get("colors") or {}))
    out["colors"] = colors
    table = dict(base.get("table") or {})
    table.update((raw.get("table") or {}))
    out["table"] = table
    google = dict(base.get("google") or {})
    google.update((raw.get("google") or {}))
    out["google"] = google
    if not out.get("logo") and slug:
        out["logo"] = f"/brand/{slug}-logo.png"
    return out
