"""Webschmiede Agency · Pakete & Preise (Cent-Beträge für Stripe)."""

from __future__ import annotations

PACKAGES = {
    "starter": {
        "id": "starter",
        "name": "Gastro Digital Starter",
        "setup_eur": 998,
        "monthly_eur": 298,
        "setup_cents": 99800,
        "monthly_cents": 29800,
        "description": "Bestellportal + Admin + Hosting",
    },
    "pro": {
        "id": "pro",
        "name": "Gastro Digital Pro",
        "setup_eur": 1980,
        "monthly_eur": 500,
        "setup_cents": 198000,
        "monthly_cents": 50000,
        "description": "Vollpaket: Portal, eigenes CRM, SMS (seven) + WhatsApp (Meta), Aktionen, Support. Ohne GHL.",
    },
    "buchhaltung_beleg": {
        "id": "buchhaltung_beleg",
        "name": "Buchhaltung Beleg-Pipeline",
        "setup_eur": 1200,
        "monthly_eur": 248,
        "setup_cents": 120000,
        "monthly_cents": 24800,
        "description": "Beleg-Postfach, Monatsmappe, CSV für DATEV/Steuerberater",
    },
    "buchhaltung_sync": {
        "id": "buchhaltung_sync",
        "name": "Buchhaltung Finanz-Sync",
        "setup_eur": 3200,
        "monthly_eur": 398,
        "setup_cents": 320000,
        "monthly_cents": 39800,
        "description": "Beleg-Pipeline + Sync Lexware/sevDesk + Fehlende-Belege-Liste",
    },
    "buchhaltung_silo": {
        "id": "buchhaltung_silo",
        "name": "Buchhaltung System-Brücke",
        "setup_eur": 5990,
        "monthly_eur": 698,
        "setup_cents": 599000,
        "monthly_cents": 69800,
        "description": "Mehr-System-Anbindung, Abgleich-Reports, Onboarding mit Kanzlei",
    },
}

AGENCY_LEGAL = {
    "name": "Webschmiede · Digitale Handwerkskunst",
    "owner": "Christian Kummetat",
    "email": "info@digitalehandwerkskunst.de",
    "vat_note": "Rechnungstellung gemäß Kleinunternehmerregelung §19 UStG (sofern zutreffend).",
}
