# Branchenbücher & Verzeichnisse für den Akquise-Krieger

Stand: Juli 2026

## Was du meintest (klassische „Bücher“)

Die alten **Branchenbücher / Gelbe Seiten / Das Örtliche / 11880** – oft Betriebe, die:
- zu klein für eine starke eigene Website wirken
- nur Telefon + Eintrag haben
- eine klare Zielgruppe haben (Dachdecker, Friseur, …)

Genau die sind für uns Gold: **Digital-Lücke + trotzdem erreichbar**.

## Quellen-Übersicht

| Quelle | Offizielle API? | Für uns | Vorteil |
|--------|-----------------|---------|---------|
| **Google Places** | ja (Key da) | aktiv | Bewertungen, Status, Tel |
| **OpenStreetMap** | ja (Overpass) | aktiv | frei, lokal |
| **Gelbe Seiten** | nein (nur Scraper/Partner) | **leichter Scan aktiv** | klassische Kleinstbetriebe |
| **Das Örtliche / 11880** | Claiming-API für Einträge, keine freie Lead-API | später / Partner | Telefonbuch-Abdeckung |
| **WLW (Wer liefert was)** | nein | optional Scrappa/Apify (Geld) | B2B-Lieferanten |
| **IHK / HWK-Verzeichnisse** | meist nein | manuell / später | Vertrauens-Signal Meisterbetrieb |
| **North Data** | ja, teuer | Hook da, Key fehlt | GF, Register, Nachfolge |
| **Kleinanzeigen** | nein | leichter Gesuch-Scan aktiv | Nachfrage |

## Immense Vorteile im Scan

1. **Abdeckung:** OSM allein verpasst viele „nur im Buch“-Betriebe  
2. **Kaufsignal:** Eintrag da, Website tot/fehlend → Add-on-Pitch  
3. **Für Kunden verkaufbar:** Handwerker-Kunde bekommt Leads in *seiner* Branche/PLZ  
4. **Differenzierung:** Die meisten Agenturen googeln manuell. Wir liefern A/B + Skript + ROI

## Geschäftsmodell: Scanner verkaufen

Ja. Drei Stufen:

| Produkt | Für wen | Preis-Idee |
|---------|---------|------------|
| **Akquise Basis** | du selbst | intern (läuft) |
| **Akquise für Kunden** | Gastro/Handwerk-Kunden | 49–149 €/Mo, Region + Branche, wöchentlicher Report |
| **White-Label Radar** | Agenturen / Franchise | Setup + Mo, ihr Branding |

Positionierung: nicht „wir scrapen Deutschland“, sondern **lokaler Radar + Freigabe + Add-on-Pitch**. Rechtlich: öffentliche Daten, Kontakt nur nach Freigabe (UWG).

## Technik-Hinweis

Gelbe Seiten & Co. haben **keine freie Lead-API**. Leichter HTML-Scan (wie jetzt) reicht für Region. Massen-Scrape über Apify/Scrappa nur mit Budget und Rate-Limits.
