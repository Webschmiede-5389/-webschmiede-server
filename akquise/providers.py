"""Erkannte Tools/Anbieter mit Kosten-Schätzung und Gegenangebot."""
from __future__ import annotations

import re
from typing import Any

# id, name, category, detect patterns, cost hint, monthly min est (€), counter pitch
CATALOG: list[dict[str, Any]] = [
    {
        "id": "lieferando",
        "name": "Lieferando / Takeaway",
        "category": "delivery",
        "patterns": ["lieferando", "takeaway.com", "deliveryhero", "foodora", "just-eat"],
        "cost": "~13–30 % Provision/Bestellung + oft 29 €/Monat",
        "monthly_min": 80,
        "monthly_typical": "150–400 €",
        "counter": "Eigenes Portal: 0 % Provision, Stammkunden-Bonuskarte, SMS-Link bei Anruf",
    },
    {
        "id": "wolt",
        "name": "Wolt",
        "category": "delivery",
        "patterns": ["wolt.com", "wolt "],
        "cost": "~25–30 % Provision",
        "monthly_min": 60,
        "monthly_typical": "100–300 €",
        "counter": "Eigene Bestell-URL, Gäste direkt, keine App-Abhängigkeit",
    },
    {
        "id": "ubereats",
        "name": "Uber Eats",
        "category": "delivery",
        "patterns": ["ubereats", "uber eats"],
        "cost": "~30 % Provision",
        "monthly_min": 50,
        "monthly_typical": "80–250 €",
        "counter": "Eigenes System, Marge bleibt im Haus",
    },
    {
        "id": "orderbird",
        "name": "Orderbird / Lightspeed",
        "category": "pos_order",
        "patterns": ["orderbird", "lightspeed", "lightspeedhq"],
        "cost": "ca. 39–89 €/Monat + Hardware",
        "monthly_min": 39,
        "monthly_typical": "50–120 €",
        "counter": "Webschmiede-Portal ergänzt oder ersetzt Online-Kanal günstiger",
    },
    {
        "id": "gastrohero",
        "name": "GastroHero",
        "category": "website_order",
        "patterns": ["gastrohero", "gastro-hero"],
        "cost": "ca. 49–99 €/Monat",
        "monthly_min": 49,
        "monthly_typical": "60–120 €",
        "counter": "Einmal-Setup + optional 49 €/Mo, kein Dauer-Abo-Zwang, volle Datenhoheit",
    },
    {
        "id": "gastronovi",
        "name": "Gastronovi",
        "category": "pos_order",
        "patterns": ["gastronovi"],
        "cost": "ca. 49 €/Monat + Kasse",
        "monthly_min": 49,
        "monthly_typical": "50–100 €",
        "counter": "Online-Bestellung separat günstiger, kein Kassensystem-Lock-in nötig",
    },
    {
        "id": "smorder",
        "name": "Smorder / Order.app",
        "category": "website_order",
        "patterns": ["smorder", "order.app"],
        "cost": "ca. 29–79 €/Monat",
        "monthly_min": 29,
        "monthly_typical": "40–90 €",
        "counter": "Eigenes Portal, einmalig statt Dauer-Miete",
    },
    {
        "id": "wordpress",
        "name": "WordPress",
        "category": "cms",
        "patterns": ["wp-content", "wordpress", "wp-includes"],
        "cost": "Hosting 5–25 €/Mo + ggf. Plugins 10–50 €/Mo",
        "monthly_min": 10,
        "monthly_typical": "15–60 €",
        "counter": "Bestell-Modul integrieren oder schlankes Portal daneben, kein Relaunch nötig",
    },
    {
        "id": "wix",
        "name": "Wix",
        "category": "cms",
        "patterns": ["wix.com", "wixsite"],
        "cost": "ca. 17–32 €/Monat",
        "monthly_min": 17,
        "monthly_typical": "20–35 €",
        "counter": "Migration zu eigenem Stack, kein Wix-Limit bei Bestellungen",
    },
    {
        "id": "jimdo",
        "name": "Jimdo",
        "category": "cms",
        "patterns": ["jimdo"],
        "cost": "ca. 9–39 €/Monat",
        "monthly_min": 9,
        "monthly_typical": "10–40 €",
        "counter": "Professioneller Auftritt + Bestellen, oft günstiger als Jimdo+Plugins langfristig",
    },
    {
        "id": "ionos",
        "name": "IONOS / 1&1",
        "category": "cms",
        "patterns": ["ionos", "1and1", "mywebsite"],
        "cost": "ca. 8–20 €/Monat",
        "monthly_min": 8,
        "monthly_typical": "10–25 €",
        "counter": "Eigene Domain + schnelles Portal auf Hetzner, DSGVO-konform",
    },
    {
        "id": "shopify",
        "name": "Shopify",
        "category": "cms",
        "patterns": ["shopify", "cdn.shopify"],
        "cost": "ab 29 €/Monat + Transaktionsgebühren",
        "monthly_min": 29,
        "monthly_typical": "35–80 €",
        "counter": "Gastro-Portal ohne Shopify-Overhead",
    },
    {
        "id": "calendly",
        "name": "Calendly / Terminbuchung",
        "category": "booking",
        "patterns": ["calendly", "cal.com", "terminland", "terminvereinbarung"],
        "cost": "0–12 €/Monat",
        "monthly_min": 0,
        "monthly_typical": "0–15 €",
        "counter": "Cal.com self-hosted inkl., keine Fremdgebühr",
    },
    {
        "id": "whatsapp_widget",
        "name": "WhatsApp-Chat",
        "category": "chat",
        "patterns": ["wa.me/", "whatsapp.com/send", "whatsapp-button"],
        "cost": "kostenlos (Meta)",
        "monthly_min": 0,
        "monthly_typical": "0 €",
        "counter": "Robert-Assistent + strukturierte Bestellung statt Chat-Chaos",
    },
    {
        "id": "tawk",
        "name": "Live-Chat (Tawk/Crisp)",
        "category": "chat",
        "patterns": ["tawk.to", "crisp.chat", "intercom"],
        "cost": "0–50 €/Monat",
        "monthly_min": 0,
        "monthly_typical": "0–30 €",
        "counter": "SMS + Bestellportal, weniger Unterbrechung in der Küche",
    },
    {
        "id": "mailchimp",
        "name": "Newsletter (Mailchimp)",
        "category": "marketing",
        "patterns": ["mailchimp", "sendinblue", "brevo"],
        "cost": "0–25 €/Monat",
        "monthly_min": 0,
        "monthly_typical": "0–20 €",
        "counter": "CRM + SMS-Aktionen im eigenen System",
    },
    {
        "id": "facebook_pixel",
        "name": "Meta Pixel / Ads",
        "category": "marketing",
        "patterns": ["facebook.net/tr", "fbq(", "meta pixel"],
        "cost": "Werbebudget variabel",
        "monthly_min": 20,
        "monthly_typical": "50–300 € Werbung",
        "counter": "Stammkunden-CRM statt Paid Ads, Bonuskarte bindet ohne Ad-Spend",
    },
    {
        "id": "google_reviews",
        "name": "Google Bewertungen aktiv",
        "category": "reputation",
        "patterns": ["google.com/maps", "maps.app.goo.gl", "bewertung schreiben"],
        "cost": "kostenlos",
        "monthly_min": 0,
        "monthly_typical": "0 €",
        "counter": "Review-Funnel nach Bestellung automatisieren (SMS)",
    },
    {
        "id": "plancraft",
        "name": "Plancraft",
        "category": "handwerk_software",
        "patterns": ["plancraft"],
        "cost": "ca. 39–99 €/Monat",
        "monthly_min": 39,
        "monthly_typical": "50–120 €",
        "counter": "Anfragen von der Website direkt ins Büro, ergänzt statt ersetzt",
    },
    {
        "id": "tooltime",
        "name": "ToolTime",
        "category": "handwerk_software",
        "patterns": ["tooltime"],
        "cost": "ca. 49–129 €/Monat",
        "monthly_min": 49,
        "monthly_typical": "60–150 €",
        "counter": "Online-Anfragen + Bewertungen als Zufluss, ToolTime bleibt fürs Büro",
    },
    {
        "id": "hero",
        "name": "Hero Software",
        "category": "handwerk_software",
        "patterns": ["hero-software", "hero software", "gethero"],
        "cost": "ca. 49–149 €/Monat",
        "monthly_min": 49,
        "monthly_typical": "70–180 €",
        "counter": "Website + Anfrage-Workflow speist Hero mit warmen Leads",
    },
    {
        "id": "openhandwerk",
        "name": "OpenHandwerk",
        "category": "handwerk_software",
        "patterns": ["openhandwerk", "open-handwerk"],
        "cost": "ca. 29–89 €/Monat",
        "monthly_min": 29,
        "monthly_typical": "40–100 €",
        "counter": "Kunden finden euch online, OpenHandwerk macht die Abwicklung",
    },
    {
        "id": "craftboxx",
        "name": "Craftboxx",
        "category": "handwerk_software",
        "patterns": ["craftboxx"],
        "cost": "ca. 39–99 €/Monat",
        "monthly_min": 39,
        "monthly_typical": "50–120 €",
        "counter": "Mehr eingehende Anfragen, weniger leere Kalender",
    },
    {
        "id": "stripe",
        "name": "Stripe / Online-Zahlung",
        "category": "payment",
        "patterns": ["stripe.com", "js.stripe.com"],
        "cost": "~1,5 % + 0,25 € pro Transaktion",
        "monthly_min": 0,
        "monthly_typical": "variabel",
        "counter": "Bereits digital aktiv, Portal-Upgrade statt Neustart",
    },
    {
        "id": "only_facebook",
        "name": "Nur Facebook/Instagram",
        "category": "social_only",
        "patterns": [],
        "cost": "0 € (versteckte Kosten: keine Bestellungen)",
        "monthly_min": 0,
        "monthly_typical": "0 €",
        "counter": "Minimal-Website + Bestelllink, ab gestaffeltem Einstieg",
    },
]


def detect_providers(text: str, host: str, sig: dict) -> list[dict]:
    hay = (text + " " + host).lower()
    host_l = host.lower()
    social_host = any(x in host_l for x in ("facebook.com", "instagram.com", "fb.com"))
    found: list[dict] = []
    seen: set[str] = set()

    for p in CATALOG:
        if p["id"] == "only_facebook":
            continue
        # CMS/Shop auf Social-Profilen oft False Positive (Facebook-Embeds)
        if social_host and p.get("category") in ("cms", "website_order", "payment"):
            continue
        for pat in p.get("patterns", []):
            if pat in hay and p["id"] not in seen:
                seen.add(p["id"])
                found.append({k: v for k, v in p.items() if k != "patterns"})
                break

    if sig.get("only_social_site") and "only_facebook" not in seen:
        p = next(x for x in CATALOG if x["id"] == "only_facebook")
        found = [{k: v for k, v in p.items() if k != "patterns"}]
        seen = {"only_facebook"}

    elif not social_host:
        for plat in sig.get("delivery_platforms") or []:
            for p in CATALOG:
                if p.get("category") != "delivery":
                    continue
                if p["id"] in seen:
                    continue
                if p["id"] in plat or plat in " ".join(p.get("patterns", [])):
                    seen.add(p["id"])
                    found.append({k: v for k, v in p.items() if k != "patterns"})
                    break

        for cms in sig.get("cms") or []:
            for p in CATALOG:
                if p["id"] == cms and p["id"] not in seen:
                    seen.add(p["id"])
                    found.append({k: v for k, v in p.items() if k != "patterns"})

    return found


def estimate_monthly_spend(providers: list[dict]) -> str:
    mins = [p.get("monthly_min", 0) for p in providers if p.get("monthly_min")]
    if not mins:
        return "0 € (kein bezahltes Tool erkannt)"
    lo = sum(mins)
    hi = int(lo * 2.2) if lo else 0
    if lo == hi:
        return f"ca. {lo} €/Monat"
    return f"ca. {lo}–{hi} €/Monat (geschätzt)"


def stack_summary(providers: list[dict]) -> str:
    if not providers:
        return "Kein Anbieter erkannt"
    parts = []
    for p in providers[:4]:
        parts.append(f"{p['name']} ({p.get('cost', '?')})")
    if len(providers) > 4:
        parts.append(f"+{len(providers) - 4} weitere")
    return " · ".join(parts)


def counter_pitch(providers: list[dict], vertical: str) -> str:
    if not providers:
        return ""
    delivery = [p for p in providers if p.get("category") == "delivery"]
    if delivery:
        d = delivery[0]
        if vertical == "gastro":
            return (
                f"Zahlt an {d['name']} ({d.get('monthly_typical', '?')}), "
                f"Eigenes Portal spart typisch 200–400 €/Mo bei aktivem Liefergeschäft. "
                f"{d.get('counter', '')}"
            )
        return f"Zahlt an {d['name']}, {d.get('counter', '')}"
    cms = [p for p in providers if p.get("category") == "cms"]
    if cms:
        return f"Nutzt {cms[0]['name']} ({cms[0].get('cost', '?')}), Upgrade statt teurer Parallel-Lösung. {cms[0].get('counter', '')}"
    return providers[0].get("counter", "")
