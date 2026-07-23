# Webschmiede — Rechnungen, Angebote & Corporate Identity

> **Agency Hub (live):** https://digitalehandwerkskunst.de/agency-hub  
> Alle Vorlagen, Farben, Logo & Markenstimme an einem Ort.

## CI-System (neu)

| Datei | URL / Pfad |
|-------|------------|
| **Agency Hub** | `/agency-hub` |
| **Designsystem** | `/ci/webschmiede-ci.css` |
| **Rechnung** | `/ci/rechnung-vorlage.html` |
| **Angebot** | `/ci/angebot-vorlage.html` |
| **Flyer** | `/ci/flyer-vorlage.html` |
| **Visitenkarte** | `/ci/visitenkarte-vorlage.html` |
| **Onboarding** | `/ci/onboarding-vorlage.html` |
| **Kunden-Handout** | `/ci/handout-vorlage.html` |
| **E-Mail-Signatur** | `/ci/email-signatur.html` |

Markenrichtlinien: `docs/agency/ci/BRAND.md`  
Domains im Onboarding (Auswahl, Wunschdomain, Auto-Kauf erst nach Klick): `docs/agency/domains-onboarding.md`  
Gastro Tischaufsteller (QR, Kunden-CI, Onboarding-Standard): `docs/agency/tischaufsteller-standard.md`  
Google Unternehmensprofil (Manager/OAuth, kein Passwort): `docs/agency/google-business-onboarding.md`  
Voice Agents (Demo eigen, Produktion Retell): `docs/agency/voice-agents.md`

## Workflow

1. Agency Hub öffnen → Vorlage wählen
2. Felder anklicken & anpassen (contenteditable)
3. **Als PDF speichern** (Drucken)
4. Per E-Mail / WhatsApp senden

## Legacy (Repo-Kopien)

Die Dateien `rechnung-vorlage.html` und `angebot-vorlage.html` in diesem Ordner sind ältere Versionen.  
**Canonical:** `app/static/ci/` (wird mit `python deploy.py` ausgerollt).

## Rechnungsnummern

Schema: `101`, `102`, … oder `WS-2026-001` — fortlaufend, lückenlos.

## Pflichtangaben Rechnung

- Name & Anschrift Anbieter + Kunde
- Rechnungsnummer, Datum
- Leistungsbeschreibung, Betrag
- USt 19 % **oder** Kleinunternehmer-Hinweis §19 UStG

Firmendaten (vorausgefüllt in CI-Vorlagen): siehe Agency Hub.
