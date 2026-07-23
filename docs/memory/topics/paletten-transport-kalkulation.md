# Kunden-Sprachnachrichten: Transport-/Paletten-Kalkulation

Stand: 2026-07-17  
Quelle: 4 WhatsApp-Sprachnachrichten (Transkription in `kunden-sprachnachrichten-2026-07-17.json`)

## Kernwunsch

Tool zur **Kalkulation** (Schwerpunkt Transport). Anfragen kommen per Mail/Telefon, oft unvollständig oder mehrere Stops auf einmal.

## Muss (MVP laut Kunde)

Ursprünglicher Gedanke: **nur Transportkosten kalkulieren**, Ausgabe als **Vorbereitung zur Prüfung durch Menschen**, nicht vollautomatisch entscheiden.

1. Start: Krefeld (Betrieb)
2. 1–6 Stationen, optimale Route (kürzeste Strecke); optional feste Reihenfolge wie vom Kunden vorgegeben
3. Rückfahrt nach Krefeld mitkalkulieren
4. Distanz + Zeit: Lkw nicht mit Pkw-Tempo (Kunde nutzt ~65 km/h Durchschnitt statt Maps 130)
5. Kostenblöcke:
   - Lkw-Leasing: ca. **0,34 €/km** (variabel, oft ~34 Cent)
   - Sprit/Diesel: aktueller Preis (Umkreis günstigster Schnitt), Verbrauch konfigurierbar
   - Fahrer + Verwaltung: zusammengefasst **50 €/h** (Fahrer; Verwaltung „mit drin“)
   - Standzeiten: eigener Betrieb **0,5 h**, Fremdbetrieb **1,75 h**
   - Maut: €/km (Cent noch offen); Ideal: mautpflichtige vs. freie km; Fallback: Gesamtkm − 10 km
6. Marge oben drauf: Basis **30 %**, kundenspezifisch z. B. **40 %**
7. Ausgabe: Transportpreis und optional Umlage auf Palettenpreis (Transport / Anzahl + Basispreis) bzw. umgekehrt Einkauf (Zahlungsbereitschaft − Transportanteil)

## Soll später / Allround

- Mail-Anfragen parsen, Unvollständiges nachfragen / aus Erfahrung ergänzen
- Palettenarten/-qualitäten (A/B/C-Bereich, B+/B− innerhalb der Grenzen)
- Abfrage an Personal: Lkw-Kapazität, Bestand vor Ort, Preis ok?
- Kundenantworten vorbereiten
- KI-Marge pro Kunde aus Historie
- Lkw-Routing-Beschränkungen (Bonus, nicht nötig)

## Haltung Kunde

Erst Monate erproben: System bereitet vor, Mensch prüft. Kein Blindflug.

## Offene Parameter (vor Bau klären)

- Firmenname / Kunden-ID bei uns
- Dieselverbrauch L/100km
- Maut-Cent/km
- Exakte Startadresse Krefeld
- Wo läuft das Tool (Agency-Portal, eigenes Dashboard, Excel-Ersatz im Browser?)
