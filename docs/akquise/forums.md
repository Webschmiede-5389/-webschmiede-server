# Foren, Pinnwände, Nachbarschaft – Scan-Landkarte

Stand: Juli 2026 · Fokus: Nachfrage für Webschmiede / lokale Betriebe

## Typen

| Typ | Beispiel | Scannbar? | Nutzen für uns |
|-----|----------|-----------|----------------|
| Nachbarschafts-App | **nebenan.de**, Nextdorf | schwer (Login + Adress-Check) | „Handwerker gesucht“, Empfehlungen – eher manuell / Watch |
| Klassiker-Kleinanzeigen | **Kleinanzeigen** | leicht (haben wir) | Website/Hilfe gesucht |
| Auftragsbörsen | **MyHammer**, Blauarbeit, **Auftragsbank** | teils HTML | echte Aufträge / Gesuche |
| Freelancer-Börsen | Twago, Freelancer.de | Watch-Links | Projekte Website/IT |
| Branchen-Foren | woodworker, fachwerk, motor-talk | RSS/HTML teils | „XY in Euskirchen gesucht“ |
| Hobby-Trödel | Angelsport-Trödel, Vereinsbörsen | wenig B2B | selten (Verein will Website) |
| Regionalforen / Pinnwand | Stadt-/Kreisforen, „Schwarzes Brett“ | gemischt | lokal, oft tot oder Login |
| Social-Gruppen | Facebook „Euskirchen verkaufen/gesucht“ | API stark limitiert | manuell heiß, Auto schwer |

## nebenan.de

Sehr nah am Kunden („Wer kennt guten Dachdecker / Website?“).  
**Aber:** nur verifizierte Nachbarn, keine öffentliche Lead-API, Scraping praktisch und rechtlich heikel.  
Für uns: **Watch / manuell** in deiner PLZ, nicht Massen-Scan.

## Hobby-Trödel (z. B. Angelsport)

Meist Privatverkauf. Für Agentur-Akquise schwach. Ausnahme: Verein/Shop sucht Webseite oder Online-Shop.

## Was sich lohnt zu scannen (Priorität)

1. Kleinanzeigen Gesuche (aktiv)  
2. Auftragsbank / MyHammer (Aufträge + Gesuche)  
3. Branchen-Foren mit „gesucht“ + Region (RSS wo möglich)  
4. Gelbe Seiten (aktiv)  
5. nebenan.de nur als menschlichen Radar

## Dark Plurality (der eigentliche Vorsprung)

Nicht die großen Bretter (Kleinanzeigen, MyHammer). Die hat jeder auf dem Schirm.
Sondern **viele kleine Oberflächen**, die einzeln dünn wirken, zusammen aber eine Nachfrage-Landschaft bilden, die kein Lead-Tool standardmäßig scannt.

### Wo die Pluralität wirklich sitzt

| Schicht | Beispiele | Intent-Dichte | Konkurrenz |
|---------|-----------|---------------|------------|
| Hobby-Trödel / Vereinsbörsen | Angelsport-Markt, Modellbau, Vereins-Pinnwand | sehr niedrig | niemand |
| Fachforen pro Gewerk | Dachdecker-, SHK-, Maler-, Friseur-Foren | mittel (gesucht + Region) | fast niemand |
| Innungen / HWK / Gewerbevereine | Mitglieder-News, „Auftrag / Nachfolger“ | hoch | niemand auto |
| Regionalpresse Anzeigen | KStA, Eifel-Blätter, Blick aktuell | mittel–hoch | niemand auto |
| Amtsblatt / kleine Ausschreibungen | Kreis, Kommune, NRW-Ausschreibungen | hoch, selten | kaum |
| Nachfolger / Übernahme | Praxis, Laden, Handwerk „abzugeben“ | sehr hoch | kaum |
| Soft-closed Social | Telegram Handwerker, Orts-FB-Gruppen | hoch | manuell |

Hobby-Bretter = immense **Anzahl** Seiten, wenig **Kaufintent** für Website/Automation.
Der Vorsprung liegt in Schicht 2–6: viele Quellen, wenige Scraper, echter B2B-Schmerz.

### Produkt-Logik

Nicht „wir scrapen Angelsport“. Sondern pro Nische ein **Dark-Radar-Paket**:
30–80 Quellen, die kein GoHighLevel und kein generischer Lead-Bot kennt.
Wöchentlich: neue Treffer → Freigabe → Anruf.
Das verkaufst du später an Kunden in ihrer Branche/Region.

### Nächste Quellen (Priorität Region Eifel/NRW)

1. **Quoka** Scan gastro / handwerk / friseur (`akquise/quoka.py`) – aktiv  
2. Fachforen „gesucht“ + Region als Watch (SHK, Dach)  
3. HWK Köln / nexxt-change Nachfolge (Watch im Katalog)  
4. Kalaydo Jobs als Wachstumssignal  
5. nebenan + Ortsgruppen nur Watch  

Katalog: `akquise/dark_sources.json` · Loader: `akquise/dark_sources.py`

## Geschäftlich

Für Kunden-Produkt: nicht „wir scrapen nebenan“, sondern **Radar aus erlaubten öffentlichen Quellen** + Freigabe. nebenan bleibt Tipp für dich persönlich in Mechernich.
