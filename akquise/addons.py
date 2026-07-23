# -*- coding: utf-8 -*-
"""Add-on-Katalog: bestehendes Tool bleibt, Webschmiede dockt an."""
from __future__ import annotations

from typing import Any

# key = provider id oder category
ADDONS: dict[str, dict[str, Any]] = {
    "lieferando": {
        "keep": "Lieferando/Wolt bleibt für Neukunden-Discovery",
        "addon": "Eigenes Bestellportal für Stammkunden + SMS-Link bei Anruf",
        "value": "Provision nur noch für App-Neukunden, Stamm läuft provisionsfrei",
        "roi_hint_monthly": 250,
    },
    "wolt": {
        "keep": "Wolt bleibt optional",
        "addon": "Eigenes Portal + Abholung",
        "value": "Marge zurückins Haus",
        "roi_hint_monthly": 180,
    },
    "ubereats": {
        "keep": "Uber Eats optional",
        "addon": "Eigenes Portal",
        "value": "Weniger 30 %-Schnitt",
        "roi_hint_monthly": 150,
    },
    "plancraft": {
        "keep": "Plancraft bleibt Büro-Software",
        "addon": "Website-Anfragen → CRM/Mail, idealerweise Export nach Plancraft",
        "value": "Mehr Aufträge in dem Tool, das schon bezahlt wird",
        "roi_hint_monthly": 400,
    },
    "tooltime": {
        "keep": "ToolTime bleibt",
        "addon": "Online-Anfrage + Bewertungs-Funnel",
        "value": "Kalender voller, weniger leere Tage",
        "roi_hint_monthly": 350,
    },
    "hero": {
        "keep": "Hero bleibt",
        "addon": "Lead-Zufluss von Website/Maps",
        "value": "Software arbeitet mit echten Anfragen",
        "roi_hint_monthly": 350,
    },
    "openhandwerk": {
        "keep": "OpenHandwerk bleibt",
        "addon": "Sichtbarkeit + Anfrage-Automation",
        "value": "Mehr Eingang, gleiche Abwicklung",
        "roi_hint_monthly": 300,
    },
    "craftboxx": {
        "keep": "Craftboxx bleibt",
        "addon": "Website + Anfragen",
        "value": "Mehr Jobs im System",
        "roi_hint_monthly": 300,
    },
    "wordpress": {
        "keep": "WordPress-Seite kann bleiben",
        "addon": "Bestell-/Anfrage-Modul oder Portal daneben + n8n",
        "value": "Kein Relaunch-Zwang, trotzdem Automation",
        "roi_hint_monthly": 200,
    },
    "wix": {
        "keep": "Wix erstmal lassen oder später migrieren",
        "addon": "Externes Portal/Formulare + WhatsApp",
        "value": "Schneller Nutzen ohne Wix-Limits",
        "roi_hint_monthly": 150,
    },
    "jimdo": {
        "keep": "Jimdo als Visitenkarte ok",
        "addon": "Professionelles Modul für Anfragen/Bestellen",
        "value": "Aus Baukasten wird Verkaufskanal",
        "roi_hint_monthly": 180,
    },
    "facebook_pixel": {
        "keep": "Meta-Ads weiterlaufen lassen",
        "addon": "Landing + Conversion + CRM-Nachfass",
        "value": "Werbeeuro kommen an statt zu verpuffen",
        "roi_hint_monthly": 300,
    },
    "only_facebook": {
        "keep": "Social bleibt für Reichweite",
        "addon": "Eigene Mini-Website + Anfrage/Bestellen",
        "value": "Kunden unter 40 springen nicht mehr ab",
        "roi_hint_monthly": 200,
    },
    "_default": {
        "keep": "Bestehende Tools bleiben",
        "addon": "Fehlenden Baustein ergänzen (Sichtbarkeit, Anfrage, Automation)",
        "value": "Kein Systemwechsel, sofortiger Mehrwert",
        "roi_hint_monthly": 150,
    },
}

CALL_SCRIPTS: dict[str, dict[str, str]] = {
    "paid_delivery_gap": {
        "title": "Lieferando/Portal-Lücke",
        "opener": "Hallo, hier ist Christian von der Webschmiede aus Mechernich. Kurz: Ich sehe, ihr seid bei Lieferando. Das ist gut für neue Gäste.",
        "pain": "Viele zahlen 13–30 % auch für Stammkunden, die euch schon kennen.",
        "addon": "Wir lassen Lieferando laufen und bauen daneben euer eigenes Bestellen. Stamm per SMS-Link, ohne Provision.",
        "ask": "Passt ein 10-Minuten-Gespräch diese Woche, ich zeige euch die Snack-House-Referenz?",
    },
    "ads_no_funnel": {
        "title": "Ads ohne Funnel",
        "opener": "Hallo, Christian von der Webschmiede. Kurz zu eurer Meta-Werbung.",
        "pain": "Wenn die Anzeige nicht auf eine klare Bestell- oder Anfrageseite geht, verpufft das Budget.",
        "addon": "Ads bleiben. Wir setzen Landing + Formular/Bestellen + Nachfass daneben.",
        "ask": "Soll ich euch in 10 Minuten zeigen, wo die Klicks gerade versickern?",
    },
    "jobs_digital_gap": {
        "title": "Personal + Digital",
        "opener": "Hallo, Christian von der Webschmiede. Ich habe gesehen, ihr sucht Verstärkung.",
        "pain": "Neue Leute sind teuer und langsam. Viele Anfragen sterben am Telefon.",
        "addon": "Wir automatisieren Anfragen/Bestellungen, damit ihr ohne neue Stelle entlastet seid.",
        "ask": "10 Minuten diese Woche, ob das bei euch greift?",
    },
    "paid_handwerk_gap": {
        "title": "Handwerk-Software ohne Leads",
        "opener": "Hallo, Christian von der Webschmiede. Ihr nutzt schon digitale Büro-Software, das ist stark.",
        "pain": "Oft fehlt nur der Zufluss: Website und Maps bringen keine strukturierten Anfragen.",
        "addon": "Software bleibt. Wir docken Anfragen von Web/Maps an.",
        "ask": "Kurztermin diese Woche?",
    },
    "trust_gap": {
        "title": "Google schwach",
        "opener": "Hallo, Christian von der Webschmiede. Kurz zu eurer Google-Sichtbarkeit.",
        "pain": "Nachbarn mit mehr Sternen und besserer Seite ziehen Anfragen ab.",
        "addon": "Review-Funnel nach Auftrag + klarer Auftritt, ohne alles umzubauen.",
        "ask": "Soll ich euch einen kostenlosen Google-Check schicken?",
    },
    "temp_closed": {
        "title": "Vorübergehend geschlossen",
        "opener": "Hallo, Christian von der Webschmiede. Ich habe gesehen, bei Google steht vorübergehend geschlossen.",
        "pain": "Wenn ihr wieder aufmacht, entscheiden Gäste in Sekunden online.",
        "addon": "Zum Restart: klarer Auftritt + Anfrage/Bestellen, damit der Schwung nicht verpufft.",
        "ask": "Passt ein kurzer Call vor der Wiedereröffnung?",
    },
    "_default": {
        "title": "Allgemein Add-on",
        "opener": "Hallo, Christian von der Webschmiede aus Mechernich.",
        "pain": "Viele Betriebe zahlen schon für Tools, aber es fehlt der eine Baustein.",
        "addon": "Wir ersetzen nichts. Wir ergänzen, was Umsatz oder Ruhe bringt.",
        "ask": "10 Minuten passen?",
    },
}


def resolve_addon(providers: list[dict], buy_signals: list[dict] | None = None) -> dict[str, Any]:
    buy_signals = buy_signals or []
    for p in providers:
        pid = p.get("id") or ""
        if pid in ADDONS:
            a = dict(ADDONS[pid])
            a["provider_id"] = pid
            a["provider_name"] = p.get("name", pid)
            return a
        cat = p.get("category") or ""
        if cat == "delivery" and "lieferando" in ADDONS:
            a = dict(ADDONS["lieferando"])
            a["provider_id"] = pid or "delivery"
            a["provider_name"] = p.get("name", "Lieferdienst")
            return a
        if cat == "handwerk_software":
            a = dict(ADDONS.get(pid) or ADDONS["plancraft"])
            a["provider_id"] = pid
            a["provider_name"] = p.get("name", pid)
            return a
    if any(s.get("id") == "ads_no_funnel" for s in buy_signals):
        a = dict(ADDONS["facebook_pixel"])
        a["provider_id"] = "facebook_pixel"
        a["provider_name"] = "Meta Ads"
        return a
    a = dict(ADDONS["_default"])
    a["provider_id"] = "_default"
    a["provider_name"] = ""
    return a


def resolve_call_script(buy_signals: list[dict] | None = None) -> dict[str, str]:
    buy_signals = buy_signals or []
    for s in buy_signals:
        sid = s.get("id") or ""
        if sid in CALL_SCRIPTS:
            return dict(CALL_SCRIPTS[sid])
    return dict(CALL_SCRIPTS["_default"])


def format_call_script(script: dict) -> str:
    return (
        f"{script.get('opener', '')} "
        f"{script.get('pain', '')} "
        f"{script.get('addon', '')} "
        f"{script.get('ask', '')}"
    ).strip()
