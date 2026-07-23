"""Anwalt WF10: Enterprise-Pack + 3-Stufen-Vertrags-Pipeline (KI-Vorpruefung, kein Anwalt-Ersatz)."""
from __future__ import annotations

import re
from datetime import date
from typing import Any

DISCLAIMER = (
    "KI-Vorpruefung und Dokumentenvorbereitung, keine Rechtsberatung. "
    "Kein Anspruch auf Wasserdichtigkeit vor Gericht. "
    "Vor Enterprise-/Grosskunden-Abschluss: zugelassenen Anwalt gegenlesen lassen "
    "(Briefing: docs/agency/vertraege/ANWALT-BRIEFING.md)."
)

HOSTING_TRUTH = {
    "provider": "Hetzner Cloud",
    "location": "Deutschland, Nuernberg (EU/DSGVO)",
    "not_location": "Nicht Helsinki/Finnland als Live-Standort behaupten (Alt-Server abgeschaltet).",
    "iso27001": "Beim Anbieter Hetzner (ISO 27001) – Zertifikat/AVV in der Hetzner Console sichern.",
    "av_kunde": "Mit dem Kunden: Webschmiede-AVV (DocuSeal Vorlage WS AVV / Kundenpaket).",
    "av_hetzner": "Mit Hetzner: Auftragsverarbeitung in der Cloud Console akzeptieren/herunterladen und ablegen.",
}

DOCUSEAL = {
    "url": "https://sign.digitalehandwerkskunst.de",
    "standard_paket": "WS Kundenpaket Auftrag AGB AVV",
    "vorlagen": [
        "docs/agency/vertraege/pdf/02-auftrag.pdf",
        "docs/agency/vertraege/pdf/03-agb.pdf",
        "docs/agency/vertraege/pdf/04-avv.pdf",
    ],
}

# System-Prompts fuer optionale LLM-Nodes (nur nach OK + Key). Standort: Nuernberg.
SYSTEM_PROMPT = """
Du bist der KI-Anwalt der Webschmiede (Vorpruefung, kein Ersatz fuer einen zugelassenen Anwalt).
Vier Durchgaenge: Haftung, DSGVO/AVV, Geld/Laufzeit, Leistung/Formalia.
Hosting-Wahrheit: Hetzner DE Nuernberg, nicht Helsinki.
Keine "wasserdicht"-Claims. Enterprise = externer Anwalt.
Zero-Retention fuer B2B-Uploads anbieten (24h Rohdaten-Loeschung).
Kein GHL. Eigenes Portal + n8n.
"""

SYSTEM_PROMPT_STUFE1 = """
Du bist der Vertrags-Architekt (Stufe 1) der Webschmiede.
Erstelle NUR den Hauptteil eines B2B-Dienstleistungsvertrags (Gegenstand, Verguetung, Laufzeit, Haftung, Mitwirkung).
Mandant: Christian Kummetat, Webschmiede / Digitale Handwerkskunst, Mechernich, B2B, USt-IdNr. DE370109681.
Hosting/Automation: eigenes Dashboard + n8n auf Hetzner DE (Nuernberg). Kein Helsinki.
Haftung: indirekte Schaeden / API-Ausfaelle Dritter (Keepa, Lexware, Meta …) begrenzen, soweit gesetzlich zulaessig;
Vorsatz/grobe Fahrlaessigkeit nicht ausschliessen.
Keine "wasserdicht"-Formulierungen. Keine AVV in dieser Stufe.
Antworte nur mit dem Vertragstext (Markdown).
"""

SYSTEM_PROMPT_STUFE2 = """
Du bist der Compliance-Waechter (Stufe 2).
Ergaenze den Entwurf um eine AVV-Anlage nach Art. 28 DSGVO.
TOMs: HTTPS/TLS, Zugangskontrolle, Hetzner Cloud Nuernberg (EU), ISO 27001 beim Anbieter,
Zero-Retention Rohdaten 24h soweit vereinbart, Subprozessoren nur soweit gebucht.
Kein Helsinki. Keine "wasserdicht"-Claims.
Antworte mit dem vollstaendigen Dokument: Hauptteil + Anlage AVV (Markdown).
"""

SYSTEM_PROMPT_STUFE3 = """
Du bist die Endkontrolle / unbestechlicher Partner (Stufe 3).
Pruefe das Gesamtdokument auf Widersprueche, Haftungsluecken, falschen Standort (Helsinki=Fehler),
fehlende AVV, fehlende Unterschrifts-/Parteienfelder, unklare Preise.
Ausgabe: Ampel (gruen/gelb/rot) + Findings-Tabelle + Checkliste A-D Kurz.
Kein Marketing. Kein "juristisch astrein". Bei Grosskunde: externer Anwalt empfohlen.
"""


def _norm_input(
    *,
    firma: str,
    kontakt: str = "",
    leistungen: str = "",
    budget: str = "",
    zero_retention: bool = True,
    brief: str = "",
) -> dict[str, Any]:
    firma = (firma or "").strip() or "Musterkunde GmbH"
    leistungen = (leistungen or "").strip() or (
        "B2B-Portal (Upload/Auswertung), Automation n8n, Hosting auf Agentur-Servern, "
        "optional Buchhaltungs-Anbindung soweit gebucht"
    )
    return {
        "firma": firma,
        "kontakt": (kontakt or "").strip(),
        "leistungen": leistungen,
        "budget": (budget or "").strip(),
        "zero_retention": bool(zero_retention),
        "brief": (brief or "").strip(),
        "today": date.today().isoformat(),
    }


def stage1_entwurf(**kwargs: Any) -> dict[str, Any]:
    """Stufe 1 – Vertrags-Architekt: Hauptteil B2B-Dienstleistungsvertrag."""
    p = _norm_input(**kwargs)
    firma, kontakt, leistungen, budget, today = (
        p["firma"],
        p["kontakt"],
        p["leistungen"],
        p["budget"],
        p["today"],
    )
    preis = budget or "[Betrag netto EUR]"
    text = f"""# B2B-Dienstleistungsvertrag
Stand: {today}

Zwischen

**Auftragnehmer:** Christian Kummetat, Einzelunternehmen Webschmiede / Digitale Handwerkskunst,
Meinertzhagener Str. 16, 53894 Mechernich, USt-IdNr. DE370109681
(„Agentur“)

und

**Auftraggeber:** {firma}
{('Ansprechpartner: ' + kontakt) if kontakt else 'Ansprechpartner: [einzutragen]'}
(„Kunde“)

## 1. Gegenstand
Die Agentur erbringt fuer den Kunden die folgenden B2B-Leistungen:

{leistungen}

Dazu gehoeren typischerweise die Bereitstellung und der Betrieb von Software-Oberflaechen (eigenes Dashboard/Portal),
Automationen (n8n) und die Anbindung an Drittsysteme, soweit ausdruecklich vereinbart
(z. B. Keepa, Lexware/Lexoffice, Messaging). Die Agentur stellt Infrastruktur und Automation bereit;
sie schuldet keinen bestimmten wirtschaftlichen Erfolg (z. B. Margen, Umsatz) und haftet nicht fuer die
inhaltliche Richtigkeit von Daten Dritter oder Drittanbieter-APIs.

## 2. Verguetung
Das vereinbarte Entgelt betraegt **{preis}** netto, soweit nicht anders schriftlich vereinbart.
Zahlungsziel und etwaige laufende Betraege ergeben sich aus Angebot/Auftrag bzw. AGB.
Aenderungsaufwand (Change Requests) wird gesondert angeboten.

## 3. Laufzeit und Kuendigung
Soweit nicht anders vereinbart, gilt die im Auftrag genannte Laufzeit.
Ordentliche Kuendigung und etwaige Verlaengerung richten sich nach Auftrag und AGB.
Bei Zahlungsverzug darf die Agentur Leistungen nach Mahnung voruebergehend aussetzen.

## 4. Haftung
Die Haftung der Agentur ist – soweit gesetzlich zulaessig – der Hoehe nach begrenzt
(Orientierung: AGB Webschmiede, u. a. Deckel bezogen auf Netto-Verguetung der letzten 12 Monate).

Ausgeschlossen bzw. beschraenkt werden – soweit gesetzlich zulaessig – Ansprueche wegen
indirekter Schaeden, entgangenen Gewinns und Folgeschaeden, insbesondere infolge von
Stoerungen oder Fehldaten Dritter (z. B. Keepa, Lexware, Meta, Stripe, Cloud-Provider).

Unberuehrt bleiben Haftung wegen Vorsatz, grober Fahrlaessigkeit, Verletzung von Leben/Koerper/Gesundheit
sowie zwingende gesetzliche Haftung.

## 5. Mitwirkung des Kunden
Der Kunde stellt rechtzeitig Zugangsdaten, Freigaben, fachliche Vorgaben und rechtmaessige Inhalte bereit.
Verzoegerungen aus fehlender Mitwirkung verlaengern Termine angemessen.

## 6. Geheimhaltung und Rechte
Beide Parteien behandeln vertrauliche Informationen vertraulich.
Nutzungsrechte an kundenspezifischen Ergebnissen und an Agentur-Frameworks richten sich nach Auftrag/AGB.

## 7. Datenschutz
Soweit personenbezogene Daten verarbeitet werden, gilt die **AVV-Anlage** (Art. 28 DSGVO)
sowie die AGB. Signatur ueber DocuSeal: {DOCUSEAL["url"]}
(Standardpaket: {DOCUSEAL["standard_paket"]}).

## 8. Schlussbestimmungen
Es gilt das Recht der Bundesrepublik Deutschland unter Ausschluss des UN-Kaufrechts.
Gerichtsstand, soweit zulaessig, am Sitz der Agentur. AGB der Agentur sind Bestandteil,
soweit einbezogen. Aenderungen beduerfen der Textform (auch DocuSeal/E-Signatur).

---
*Stufe 1 Entwurf – {DISCLAIMER}*
"""
    return {
        "ok": True,
        "agent": "anwalt",
        "stage": 1,
        "stage_name": "vertrags_architekt",
        "firma": firma,
        "params": p,
        "document": text.strip(),
        "system_prompt": SYSTEM_PROMPT_STUFE1.strip(),
        "disclaimer": DISCLAIMER,
        "rechtskraft": False,
        "auto_send": False,
    }


def stage2_avv(entwurf: str | None = None, **kwargs: Any) -> dict[str, Any]:
    """Stufe 2 – Compliance-Waechter: AVV anhaengen / DSGVO-Haertung."""
    p = _norm_input(**kwargs)
    if not (entwurf or "").strip():
        entwurf = stage1_entwurf(**kwargs)["document"]
    retention = (
        "Rohdaten/Kunden-Uploads unterliegen einer Zero-Retention-Policy: "
        "Loeschung der Rohdatei und Rohzeilen spaetestens 24 Stunden nach Ablauf der Frist "
        "(Portal-Default), soweit nicht gesetzliche Aufbewahrungspflichten entgegenstehen. "
        "Aggregierte Auswertungs-Kennzahlen duerfen verbleiben."
        if p["zero_retention"]
        else "Loeschung bzw. Rueckgabe nach Vertragsende bzw. auf Weisung des Kunden "
        "innerhalb von 30 Tagen, soweit keine gesetzlichen Aufbewahrungspflichten."
    )
    avv = f"""
---

# Anlage: Auftragsverarbeitungsvertrag (AVV) nach Art. 28 DSGVO
Stand: {p["today"]}
Kunde / Verantwortlicher: {p["firma"]}
Auftragsverarbeiter: Christian Kummetat (Webschmiede / Digitale Handwerkskunst)

## A1. Gegenstand und Dauer
Gegenstand ist die Verarbeitung personenbezogener Daten im Rahmen der unter § 1 des Hauptvertrags
beschriebenen Leistungen: {p["leistungen"]}
Dauer: fuer die Laufzeit des Hauptvertrags zuzueglich der Loeschfristen.

## A2. Art und Zweck der Verarbeitung
Zweck: Betrieb von Portal/Dashboard, Automationen (n8n), Auswertung von Händler-/Listen-Uploads,
optional Buchhaltungs-Anbindung und Messaging, soweit gebucht.
Kategorien: je nach Leistung z. B. Kontaktdaten, Auftrags-/Listeninhalte, technische Logs.
Betroffene: Mitarbeiter/Kunden des Kunden und sonstige betroffene Personen in den uebermittelten Daten.

## A3. Speicherort und Unterauftragsverarbeiter
Primaerer Speicherort: **Hetzner Cloud, Rechenzentrum Deutschland (Nuernberg), EU**.
Anbieter mit ISO-27001-Zertifizierung. {HOSTING_TRUTH["not_location"]}
Weitere Unterauftragsverarbeiter nur soweit eingesetzt/gebucht (z. B. DocuSeal, Meta, Stripe, seven.io)
und in der jeweils aktuellen AVV-Liste der Agentur genannt; Widerspruchsrecht des Kunden nach AVV-Standard.

## A4. Technische und organisatorische Massnahmen (TOMs)
- Uebertragung: HTTPS/TLS
- Zugang: authentisierte Admin-/Portal-Zugänge, Secrets nur serverseitig
- Automation: n8n mit Credential-Verschluesselung (N8N_ENCRYPTION_KEY); Execution-Logs gehaertet
- Trennung von Mandanten-/Job-Daten im Portal soweit technisch vorgesehen
- {retention}

Hinweis zur Verschluesselung at rest: Provider-Seite Hetzner; App-Layer-DB-Verschluesselung
ist kein pauschaler Live-Anspruch, sofern nicht gesondert vereinbart.

## A5. Weisungen, Betroffenenrechte, Loeschung
Der Auftragsverarbeiter verarbeitet Daten nur auf dokumentierte Weisung des Kunden.
Unterstuetzung bei Betroffenenrechten (Auskunft, Loeschung, Berichtigung) im zumutbaren Umfang.
Nach Ende der Verarbeitung: Loeschung oder Rueckgabe nach Weisung / AVV-Standard (Orientierung 30 Tage).

## A6. Nachweis und Audits
Nachweise zu TOMs auf Anfrage in angemessenem Umfang. Audits nach AVV-Standard der Webschmiede-Vorlage.

## A7. Schluss
Im Widerspruch zwischen Hauptvertrag und AVV gehen die datenschutzrechtlichen Pflichten der AVV vor,
soweit sie zwingend sind. Signatur empfohlen ueber {DOCUSEAL["url"]}.

---
*Stufe 2 AVV – {DISCLAIMER}*
"""
    full = (entwurf or "").rstrip() + "\n" + avv.strip() + "\n"
    # Falsche Live-Standort-Claims korrigieren (Negationen wie "nicht Helsinki" behalten)
    full = re.sub(
        r"(?i)\b(rechenzentrum|standort|server|hosting)\s+[^\n]{0,60}\bhelsinki\b",
        r"\1 Deutschland (Nuernberg)",
        full,
    )
    full = re.sub(
        r"(?i)\bhelsinki\s*\(finnland(?:,\s*eu)?\)",
        "Nuernberg (Deutschland, EU)",
        full,
    )
    return {
        "ok": True,
        "agent": "anwalt",
        "stage": 2,
        "stage_name": "compliance_waechter",
        "firma": p["firma"],
        "params": p,
        "document": full,
        "avv_only": avv.strip(),
        "system_prompt": SYSTEM_PROMPT_STUFE2.strip(),
        "disclaimer": DISCLAIMER,
        "hosting": HOSTING_TRUTH,
        "rechtskraft": False,
        "auto_send": False,
    }


def stage3_endkontrolle(document: str, **kwargs: Any) -> dict[str, Any]:
    """Stufe 3 – Endkontrolle: Checkliste, Ampel, Findings (deterministisch)."""
    p = _norm_input(**kwargs)
    doc = document or ""
    findings: list[dict[str, str]] = []
    checks: list[dict[str, str]] = []

    def mark(cid: str, ok: bool, note: str, severity: str = "mittel") -> None:
        checks.append({"id": cid, "status": "ok" if ok else "fail", "note": note})
        if not ok:
            findings.append(
                {
                    "schwere": severity,
                    "stelle": cid,
                    "problem": note,
                    "empfehlung": "Vor Kundenversand nachschaerfen / DocuSeal-Vorlage nutzen",
                }
            )

    low = doc.lower()
    mark("A1", "haftung" in low, "Haftungsabschnitt vorhanden?", "hoch")
    mark("A2", any(x in low for x in ("indirekt", "entgangen", "folgeschaden", "folgeschaeden")), "Indirekte Schaeden / entgangener Gewinn adressiert?", "hoch")
    mark("A3", any(x in low for x in ("vorsatz", "grober fahrl", "grobe fahrl")), "Vorsatz/grobe Fahrlaessigkeit nicht pauschal ausgeschlossen?", "kritisch")
    mark("A4", any(x in low for x in ("keepa", "lexware", "lexoffice", "dritt", "api")), "Drittanbieter-APIs erwaehnt?", "mittel")
    mark("B1", "art. 28" in low or "auftragsverarbeit" in low or "avv" in low, "AVV / Art. 28 vorhanden?", "kritisch")
    mark("B3", "https" in low or "tls" in low, "TOM Verschluesselung in transit?", "hoch")
    mark("B4", "nuernberg" in low or "nürnberg" in low or "nuremberg" in low, "Standort Nuernberg genannt?", "kritisch")
    # Warnhinweise ("nicht Helsinki") OK; positive Live-Standort-Behauptung nicht
    scrubbed = re.sub(
        r"(?i)(nicht|kein|keinen|keine|nie)\s+[^\n.]{0,40}(helsinki|finnland)",
        " ",
        low,
    )
    scrubbed = re.sub(r"(?i)(helsinki|finnland)[^\n.]{0,40}(nicht|kein)\s+behaupten", " ", scrubbed)
    bad_helsinki = bool(re.search(r"helsinki|finnland", scrubbed))
    mark("B4b", not bad_helsinki, "Kein falscher Live-Standort Helsinki/Finnland", "kritisch")
    mark("B6", "loesch" in low or "lösch" in low or "retention" in low or "zero-retention" in low, "Loeschung/Retention geregelt?", "hoch")
    mark("C1", bool(p["budget"]) or "betrag" in low or "€" in doc or "eur" in low, "Verguetung/Preis erkennbar?", "hoch")
    mark("D1", bool(p["leistungen"]) and len(doc) > 400, "Leistungsgegenstand konkret genug?", "mittel")
    mark("D7", p["firma"].lower() in low, "Kundenfirma im Text?", "hoch")
    mark("D9", "anlage" in low or "avv" in low, "Anlage AVV referenziert/enthalten?", "hoch")
    claim_scrub = re.sub(
        r"(?i)kein anspruch auf wasserdichtigkeit|keine \"wasserdicht\"|keine 'wasserdicht'",
        " ",
        low,
    )
    mark(
        "X1",
        not bool(re.search(r"wasserdicht|absolut rechtssicher|juristisch astrein", claim_scrub)),
        "Keine unserioesen Wasserdicht-Claims im Text",
        "mittel",
    )

    crit = sum(1 for f in findings if f["schwere"] == "kritisch")
    hoch = sum(1 for f in findings if f["schwere"] == "hoch")
    if crit:
        ampel = "rot"
    elif hoch or findings:
        ampel = "gelb"
    else:
        ampel = "gruen"

    protokoll = "\n".join(
        [
            f"# Vertrags-Pruefprotokoll (Stufe 3)",
            f"Stand: {p['today']}",
            f"Dokument: Pipeline fuer {p['firma']}",
            "",
            "## Disclaimer",
            DISCLAIMER,
            "",
            f"## Ampel",
            f"Gesamt: {ampel}",
            f"Kurz: {len(findings)} Finding(s), davon {crit} kritisch.",
            "",
            "## Findings",
            "| # | Schwere | Stelle | Problem | Empfehlung |",
            "|---|---------|--------|---------|------------|",
        ]
    )
    if not findings:
        protokoll += "\n| – | ok | – | Keine automatischen Treffer | Trotzdem DocuSeal-Vorlage + bei Enterprise Anwalt |"
    else:
        for i, f in enumerate(findings, 1):
            protokoll += (
                f"\n| {i} | {f['schwere']} | {f['stelle']} | {f['problem']} | {f['empfehlung']} |"
            )
    protokoll += "\n\n## Checkliste\n"
    for c in checks:
        icon = "OK" if c["status"] == "ok" else "FAIL"
        protokoll += f"- [{icon}] {c['id']}: {c['note']}\n"
    protokoll += (
        "\n## Naechster Schritt\n"
        + (
            "Kritische Punkte beheben, dann DocuSeal Kundenpaket senden; Enterprise: externer Anwalt."
            if ampel == "rot"
            else "DocuSeal-Felder befuellen und vor Grosskunde ANWALT-BRIEFING nutzen."
            if ampel == "gelb"
            else "Technisch gruen – trotzdem kein Ersatz fuer Anwaltsfreigabe bei Enterprise."
        )
    )

    return {
        "ok": True,
        "agent": "anwalt",
        "stage": 3,
        "stage_name": "endkontrolle",
        "firma": p["firma"],
        "params": p,
        "document": doc,
        "ampel": ampel,
        "findings": findings,
        "checklist": checks,
        "protokoll": protokoll,
        "system_prompt": SYSTEM_PROMPT_STUFE3.strip(),
        "disclaimer": DISCLAIMER,
        "rechtskraft": False,
        "auto_send": False,
        "freigabe_fuer_kundenversand_technisch": ampel == "gruen",
        "empfehlung_externer_anwalt": True,
    }


def pipeline_3_stufen(**kwargs: Any) -> dict[str, Any]:
    """Komplette Kette: Entwurf -> AVV -> Endkontrolle. Kein Auto-Send."""
    s1 = stage1_entwurf(**kwargs)
    s2 = stage2_avv(entwurf=s1["document"], **kwargs)
    s3 = stage3_endkontrolle(s2["document"], **kwargs)
    pack = enterprise_pack(**kwargs)
    combined = (
        s2["document"].rstrip()
        + "\n\n"
        + s3["protokoll"]
        + "\n\n---\n## DocuSeal-Hinweis\n"
        + f"Signatur: {DOCUSEAL['url']} · Paket: {DOCUSEAL['standard_paket']}\n"
        + f"Felder: {pack['docuseal_fields']}\n"
    )
    return {
        "ok": True,
        "agent": "anwalt",
        "mode": "pipeline_3_stufen",
        "workflow": 10,
        "disclaimer": DISCLAIMER,
        "firma": s1["firma"],
        "hosting": HOSTING_TRUTH,
        "stages": {
            "1_entwurf": {"document": s1["document"], "prompt": s1["system_prompt"]},
            "2_avv": {"document": s2["document"], "prompt": s2["system_prompt"]},
            "3_endkontrolle": {
                "ampel": s3["ampel"],
                "findings": s3["findings"],
                "protokoll": s3["protokoll"],
                "prompt": s3["system_prompt"],
            },
        },
        "document": s2["document"],
        "protokoll": s3["protokoll"],
        "ampel": s3["ampel"],
        "findings": s3["findings"],
        "docuseal": DOCUSEAL,
        "docuseal_fields": pack["docuseal_fields"],
        "markdown": combined,
        "rechtskraft": False,
        "auto_send": False,
        "llm_nodes": False,
        "hinweis_llm": (
            "Keine Claude/GPT-Nodes ohne Christians OK und API-Key. "
            "Pipeline laeuft deterministisch auf dem Agency-Server (Nuernberg-Wahrheit, Checkliste)."
        ),
        "next_step": (
            "Ampel rot: Findings beheben."
            if s3["ampel"] == "rot"
            else "DocuSeal befuellen; Hetzner-AVV in Akten; bei Enterprise Anwalt."
        ),
        "system_prompts": {
            "stufe1": SYSTEM_PROMPT_STUFE1.strip(),
            "stufe2": SYSTEM_PROMPT_STUFE2.strip(),
            "stufe3": SYSTEM_PROMPT_STUFE3.strip(),
        },
    }


def enterprise_pack(
    *,
    firma: str,
    kontakt: str = "",
    leistungen: str = "",
    budget: str = "",
    zero_retention: bool = True,
    brief: str = "",
) -> dict[str, Any]:
    p = _norm_input(
        firma=firma,
        kontakt=kontakt,
        leistungen=leistungen,
        budget=budget,
        zero_retention=zero_retention,
        brief=brief,
    )
    firma = p["firma"]
    leistungen = p["leistungen"]
    budget = p["budget"]
    kontakt = p["kontakt"]
    today = p["today"]
    retention = (
        "24 Stunden Zero-Retention fuer Upload-Rohdaten (Datei + Zeilen), Aggregat-Stats duerfen bleiben."
        if p["zero_retention"]
        else "Standard-Retention laut AVV (Loeschung nach Vertragsende / 30 Tage nach Aufforderung)."
    )

    docuseal_fields = {
        "Kunde Firma": firma,
        "Kunde Kontakt": kontakt or "[Ansprechpartner]",
        "Leistungen": leistungen[:200],
        "Leistungen AVV": leistungen[:120],
        "AVV Nummer": f"AVV-{date.today().year}-",
        "Honorar / Preis": budget or "[Betrag netto]",
        "Hosting Hinweis": "Hetzner Cloud, Rechenzentrum Deutschland (Nuernberg), Anbieter ISO 27001",
        "Zero Retention": "ja" if p["zero_retention"] else "nein / AVV-Standard",
    }

    avv_anlage = f"""# AVV-Anlage (Entwurf fuer DocuSeal-Felder / Kundeninfo)
Stand: {today}
Kunde: {firma}

## 1. Gegenstand
Verarbeitung personenbezogener Daten im Rahmen: {leistungen}

## 2. Speicherort
Hetzner Cloud, Deutschland (Nuernberg), EU. Anbieter mit ISO-27001-Zertifizierung.
Kein Live-Betrieb auf Nicht-EU-Bastel-Servern.

## 3. TOMs (Kurz)
- Uebertragung: HTTPS/TLS
- Zugang: authentisierte Portale / Admin, Secrets nur serverseitig
- Automation: n8n auf Agentur-Server; Credentials verschluesselt (N8N_ENCRYPTION_KEY)
- Unterauftragsverarbeiter: Hetzner; weitere nur soweit gebucht (DocuSeal, Meta, Stripe, …) laut AVV-Liste

## 4. Loeschung / Retention
{retention}
Nach Vertragsende: Loeschung bzw. Rueckgabe gemaess AVV (Vorlage: 30 Tage nach Aufforderung, soweit keine gesetzlichen Aufbewahrungspflichten).

## 5. Betroffenenrechte
Unterstuetzung des Verantwortlichen (Kunde) bei Auskunft, Loeschung, Berichtigung nach Art. 28 DSGVO.

## Disclaimer
{DISCLAIMER}
"""

    hauptvertrag = f"""# B2B-Dienstleistung (Hinweisblatt fuer DocuSeal Auftrag)
Stand: {today}
Kunde: {firma}
Kontakt: {kontakt or "[offen]"}
Honorar: {budget or "[offen]"}

Leistung (Kurz): {leistungen}

Dokumente zum Signieren (ein Link empfohlen):
- {DOCUSEAL["standard_paket"]}
- URL: {DOCUSEAL["url"]}

Inhaltlich nutzen wir die bestehenden Vorlagen Auftrag + AGB + AVV.
Dieses Pack fuellt Felder vor und erklaert TOMs/Standort – es ersetzt keine Anwaltstexte.
"""

    vendor = [
        {"frage": "Hosting-Standort?", "antwort": HOSTING_TRUTH["location"]},
        {"frage": "AVV mit Hosting-Anbieter?", "antwort": HOSTING_TRUTH["av_hetzner"]},
        {"frage": "AVV mit Kunde?", "antwort": "DocuSeal WS AVV / Kundenpaket"},
        {"frage": "Encryption in transit?", "antwort": "HTTPS/TLS"},
        {
            "frage": "Encryption at rest (App)?",
            "antwort": "Noch keine App-Layer-DB-Verschluesselung; ehrlich angeben. Provider-Seite Hetzner.",
        },
        {"frage": "Zero-Retention Uploads?", "antwort": "ja" if p["zero_retention"] else "optional aus"},
        {"frage": "n8n Execution-Logs?", "antwort": "Prune/Save-on-success haerten (siehe harden_n8n_logs)"},
        {"frage": "Subprozessoren?", "antwort": "AVV-Liste; nur soweit gebucht"},
    ]

    checklist_christian = [
        "Hetzner AVV in Console laden und lokal ablegen (docs/agency/hetzner-avv.md)",
        "DocuSeal Kundenpaket mit Feldern oben befuellen und senden",
        "Bei Enterprise: ANWALT-BRIEFING + PDFs an echten Anwalt",
        "Kunde ueber Zero-Retention und Standort Nuernberg informieren (nicht Helsinki)",
    ]

    markdown = "\n".join(
        [
            f"# Enterprise-Paket Anwalt (KI) – {firma}",
            f"Stand: {today}",
            "",
            "## Disclaimer",
            DISCLAIMER,
            "",
            "## Hosting-Wahrheit",
            f"- {HOSTING_TRUTH['location']}",
            f"- {HOSTING_TRUTH['not_location']}",
            f"- {HOSTING_TRUTH['iso27001']}",
            "",
            "## DocuSeal-Felder",
            *[f"- **{k}:** {v}" for k, v in docuseal_fields.items()],
            "",
            "## Vendor Assessment (Kurz)",
            *[f"- {v['frage']} -> {v['antwort']}" for v in vendor],
            "",
            "## Todos Christian",
            *[f"{i+1}. {c}" for i, c in enumerate(checklist_christian)],
            "",
            "## AVV-Anlage (Entwurf)",
            avv_anlage,
            "",
            "## Hauptvertrag-Hinweis",
            hauptvertrag,
            "",
            "## 3-Stufen-Pipeline",
            "POST /api/agency/anwalt/pipeline  (Entwurf -> AVV -> Endkontrolle)",
        ]
    )
    if brief:
        markdown += f"\n\n## Rohbriefing\n{brief[:2000]}\n"

    return {
        "ok": True,
        "agent": "anwalt",
        "mode": "enterprise_pack",
        "workflow": 10,
        "disclaimer": DISCLAIMER,
        "firma": firma,
        "kontakt": kontakt,
        "leistungen": leistungen,
        "budget": budget,
        "zero_retention": p["zero_retention"],
        "hosting": HOSTING_TRUTH,
        "docuseal": DOCUSEAL,
        "docuseal_fields": docuseal_fields,
        "vendor_assessment": vendor,
        "avv_anlage_markdown": avv_anlage,
        "hauptvertrag_hinweis": hauptvertrag,
        "todos_christian": checklist_christian,
        "next_step": checklist_christian[0],
        "rechtskraft": False,
        "markdown": markdown,
        "system_prompt": SYSTEM_PROMPT.strip(),
        "auto_send": False,
    }


def review_stub(text: str) -> dict[str, Any]:
    return {
        "ok": True,
        "agent": "anwalt",
        "mode": "review_hint",
        "workflow": 10,
        "disclaimer": DISCLAIMER,
        "hinweis": (
            "Vollpruefung: Cursor Skill anwalt + checkliste.md. "
            "3-Stufen: POST /api/agency/anwalt/pipeline"
        ),
        "text_preview": (text or "")[:400],
        "system_prompt": SYSTEM_PROMPT.strip(),
    }
