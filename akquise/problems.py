"""Versteckte Probleme erkennen + Webschmiede-Lösung (Automation/Produkt)."""
from __future__ import annotations

from typing import Any

# id, label, category, solution_type, solution_label, automation
PROBLEM_CATALOG: list[dict[str, Any]] = [
    {
        "id": "invisible_google",
        "label": "Auf Google praktisch unsichtbar",
        "category": "sichtbarkeit",
        "solution_type": "website",
        "solution": "Eigene Website + Google Business optimieren, bei „Restaurant + Ort\" gefunden werden",
        "automation": "n8n: Google-Review-Anfrage nach Besuch",
    },
    {
        "id": "only_social",
        "label": "Nur Facebook/Instagram, kein eigener Auftritt",
        "category": "sichtbarkeit",
        "solution_type": "website",
        "solution": "Professionelle Website statt Meta-Profil, Gäste unter 40 springen bei FB ab",
        "automation": "Link-in-Bio → Bestellportal",
    },
    {
        "id": "lieferando_bleed",
        "label": "Zahlt Lieferando-Provision (oft ohne es zu wissen)",
        "category": "marge",
        "solution_type": "order_portal",
        "solution": "Eigenes Bestellportal, 0 % Provision, Stammkunden binden (Referenz Snack House)",
        "automation": "SMS mit Bestelllink bei Anruf (seven.io)",
    },
    {
        "id": "no_online_order",
        "label": "Kein Online-Bestellen, Umsatz bleibt liegen",
        "category": "umsatz",
        "solution_type": "order_portal",
        "solution": "Bestellportal Abholung/Lieferung, Gäste bestellen wenn Telefon besetzt",
        "automation": "Admin-Dashboard + Drucker/Bestell-Push",
    },
    {
        "id": "phone_bottleneck",
        "label": "Telefon-Chaos in Stoßzeiten",
        "category": "personal",
        "solution_type": "automation",
        "solution": "Online-Bestellung + SMS-Link bei Anruf, Küche telefoniert nicht mehr",
        "automation": "Workflow: Anruf → SMS Bestelllink → CRM-Eintrag",
    },
    {
        "id": "staff_shortage",
        "label": "Personalmangel / sucht Verstärkung",
        "category": "personal",
        "solution_type": "automation",
        "solution": "Digital entlasten statt mehr Köpfe, Bestellen, FAQ, Bewertungen automatisch",
        "automation": "Robert-Assistent für Öffnungszeiten/Allergene",
    },
    {
        "id": "no_loyalty",
        "label": "Keine Stammkunden-Bindung",
        "category": "umsatz",
        "solution_type": "crm",
        "solution": "Digitale Bonuskarte (10 Bestellungen = Gratis-Getränk), Gäste kommen wieder",
        "automation": "CRM + automatische Promo-SMS",
    },
    {
        "id": "bad_reviews",
        "label": "Schwache Google-Bewertungen",
        "category": "vertrauen",
        "solution_type": "reviews",
        "solution": "Review-Funnel nach Bestellung, zufriedene Gäste bewerten, Negatives intern",
        "automation": "n8n: Bestellung abgeschlossen → SMS Review-Link",
    },
    {
        "id": "low_reviews",
        "label": "Kaum Google-Bewertungen, Konkurrenz wirkt stärker",
        "category": "vertrauen",
        "solution_type": "reviews",
        "solution": "Lokal stärkster Partner: systematisch Bewertungen sammeln",
        "automation": "Monatsreport Bewertungen + Ranking",
    },
    {
        "id": "not_mobile",
        "label": "Website nicht mobil, junge Gäste abspringen",
        "category": "technik",
        "solution_type": "website",
        "solution": "Mobil-first Portal, 70 % bestellen am Handy",
        "automation": "PWA optional (App-Feeling ohne App-Store)",
    },
    {
        "id": "pdf_menu",
        "label": "PDF-Speisekarte, niemand liest das am Handy",
        "category": "technik",
        "solution_type": "website",
        "solution": "Digitale Speisekarte + QR am Tisch",
        "automation": "Admin: Preis ändern → sofort live",
    },
    {
        "id": "tradition_stagnation",
        "label": "„Läuft schon immer so“, Umsatz stagniert unsichtbar",
        "category": "mindset",
        "solution_type": "beratung",
        "solution": "Zahlen zeigen: Nachbarn mit Portal holen Abhol-Umsatz, 15 Min. ROI-Gespräch",
        "automation": "Kostenloser Digital-Check vor Ort",
    },
    {
        "id": "pub_no_takeaway",
        "label": "Kneipe/Pub ohne Abhol- oder Bestellkanal",
        "category": "umsatz",
        "solution_type": "order_portal",
        "solution": "Abhol-Bestellung für Essen/Getränke, neuer Umsatz ohne neues Lokal",
        "automation": "Speisekarte online + Click & Collect",
    },
    {
        "id": "no_leads_online",
        "label": "Kein Online-Anfrage-System",
        "category": "umsatz",
        "solution_type": "automation",
        "solution": "Anfrageformular → CRM → Auto-Antwort, keine Anfrage verloren",
        "automation": "n8n: Formular → E-Mail + SMS Bestätigung",
    },
    {
        "id": "slow_site",
        "label": "Langsame Website, Gäste brechen ab",
        "category": "technik",
        "solution_type": "website",
        "solution": "Schnelles Hetzner-Portal statt Baukasten",
        "automation": "Monitoring + monatlicher Speed-Check",
    },
    {
        "id": "meta_ads_no_conversion",
        "label": "Wirbt auf Meta, aber keine eigene Conversion-Seite",
        "category": "marketing",
        "solution_type": "website",
        "solution": "Werbung + Landingpage + Bestellen/Termin, sonst verpufft das Budget",
        "automation": "Meta-Pixel + Portal-Funnel",
    },
    {
        "id": "local_rank_losing",
        "label": "Konkurrenz in der Stadt digital vorne",
        "category": "wettbewerb",
        "solution_type": "website",
        "solution": "Lokal stärkster Partner werden, Maps + Portal + Reviews",
        "automation": "Quartals-Ranking-Report",
    },
]


def _has_tradition_signals(sig: dict) -> bool:
    return bool(sig.get("tradition_signals"))


def _is_pub_like(lead: dict) -> bool:
    a = (lead.get("amenity") or "").lower()
    name = (lead.get("name") or "").lower()
    return a in ("bar", "pub", "biergarten") or any(x in name for x in ("kneipe", "pub", "pief", "brauhaus", "taverne"))


def detect_problems(lead: dict, sig: dict, vertical_id: str) -> list[dict]:
    gp = lead.get("google_places") or {}
    reviews = int(gp.get("user_ratings_total") or 0)
    rating = gp.get("rating")
    providers = sig.get("providers") or []
    has_delivery = bool(sig.get("delivery_platforms")) or any(p.get("category") == "delivery" for p in providers)
    found: list[dict] = []

    def add(pid: str, severity: str = "medium", hidden: bool = False):
        spec = next((p for p in PROBLEM_CATALOG if p["id"] == pid), None)
        if not spec:
            return
        if any(x["id"] == pid for x in found):
            return
        found.append({**spec, "severity": severity, "hidden": hidden})

    if sig.get("only_social_site"):
        add("only_social", "high", hidden=False)
        add("invisible_google", "high", hidden=True)
    elif not sig.get("has_website"):
        add("invisible_google", "high")
        add("only_social", "high")

    if has_delivery:
        add("lieferando_bleed", "high", hidden=True)

    if sig.get("checked") and not sig.get("order_signals") and sig.get("has_website") and not sig.get("only_social_site"):
        add("no_online_order", "medium")

    if _is_pub_like(lead) and not sig.get("order_signals"):
        add("pub_no_takeaway", "medium", hidden=True)

    if sig.get("job_signals"):
        add("staff_shortage", "high")
        if lead.get("phone"):
            add("phone_bottleneck", "high", hidden=True)

    if not sig.get("delivery_platforms") and not sig.get("order_signals"):
        add("no_loyalty", "low", hidden=True)

    if rating and float(rating) < 4.0 and reviews > 5:
        add("bad_reviews", "high")
    elif reviews < 20 and sig.get("has_website"):
        add("low_reviews", "medium", hidden=True)

    if sig.get("has_website") and not sig.get("mobile_viewport") and sig.get("checked"):
        add("not_mobile", "medium")

    if sig.get("pdf_menu"):
        add("pdf_menu", "medium")

    if _has_tradition_signals(sig) and (sig.get("only_social_site") or not sig.get("order_signals")):
        add("tradition_stagnation", "high", hidden=True)

    if sig.get("load_time_ms", 0) > 4000:
        add("slow_site", "low")

    if vertical_id == "handwerk" and sig.get("checked") and not sig.get("order_signals"):
        add("no_leads_online", "high")

    if has_delivery or (sig.get("only_social_site") and reviews > 30):
        add("local_rank_losing", "medium", hidden=True)

    lr = lead.get("local_rank") or {}
    if lr.get("ahead", 0) >= 2:
        add("local_rank_losing", "high", hidden=False)

    if sig.get("runs_facebook_ads") and (sig.get("only_social_site") or not sig.get("order_signals")):
        add("meta_ads_no_conversion", "high", hidden=False)

    severity_order = {"high": 0, "medium": 1, "low": 2}
    found.sort(key=lambda x: severity_order.get(x["severity"], 9))
    return found[:6]


def problems_summary(problems: list[dict]) -> str:
    if not problems:
        return "Kein klares Problem erkannt"
    return " · ".join(p["label"][:45] for p in problems[:3])


def solutions_summary(problems: list[dict]) -> str:
    if not problems:
        return ""
    parts = []
    for p in problems[:3]:
        parts.append(f"{p['solution_type'].upper()}: {p['solution'][:80]}")
    return " | ".join(parts)
