# Datenquellen für Akquise-Anreicherung

## Bereits aktiv (v3)

| Quelle | Was | Kontakt | Intention |
|--------|-----|---------|-----------|
| **OpenStreetMap** | Name, Adresse, Tel, Website | Tel | — |
| **Website-Crawl** | Lieferando, Jobs, Bestellen, CMS | E-Mail (Seite) | Signale |
| **Impressum/Kontakt** | Inhaber/GF-Name, Tel, Mail, GmbH/ e.K. | **Name + Mail + Tel** | — |
| **Google Places** (optional) | Bewertung, Anzahl Reviews | — | Vertrauen |
| **Intent-Engine** | — | Wen ansprechen | **Spalte rechts** |

## Später / optional (kostenpflichtig oder manuell)

| Quelle | Nutzen | Kontaktperson | Kosten |
|--------|--------|---------------|--------|
| **North Data API** | GF-Name, Register, Netzwerk | Name (selten Tel/Mail) | ~500 €/Mo |
| **Handelsregister** (bundesweite.de) | Rechtsform, Vertretung | Name | Einzelabruf |
| **Bundesanzeiger** | Publikationen, Insolvenz | — | North Data / manuell |
| **Gewerbeamts-Meldungen** | Neueröffnung | — | regional schwer |
| **Indeed/Kleinanzeigen** | Stellen = Personal-Intent | — | API / manuell |
| **Facebook Seiten-Info** | Tel, Öffnungszeiten | selten Person | Graph API limitiert |
| **LinkedIn** | Entscheider | **nicht automatisieren** | Sales Navigator |

## Intention-Typen im Report

| Code | Bedeutung | Ansprache |
|------|-----------|-----------|
| `provision` | Nutzt Lieferando & Co. | Marge behalten |
| `digital_neu` | Keine / nur Social-Website | Komplett-Paket |
| `entlastung` | Sucht Personal | SMS + Online-Bestellung |
| `umsatz` | Kein eigenes Bestellen | Stammkunden + Portal |
| `vertrauen` | Schwaches Google / HTTPS | Sichtbarkeit |
| `standard` | Allgemein | Erstgespräch + Referenz |

## Recht

Öffentliche Quellen (Impressum, OSM) für B2B-Akquise üblich. Kein Massen-Mail — **Freigabe vor Kontakt** (UWG).
