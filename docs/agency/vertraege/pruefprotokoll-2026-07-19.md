# Vertrags-Prüfprotokoll
Stand: 2026-07-19  
Dokument: Kundenpaket Auftrag + AGB B2B + AVV (`docs/agency/vertraege/` 02 / 03 / 04)  
Rolle: Webschmiede = Auftragnehmer / Auftragsverarbeiter

## Disclaimer
KI-Vorprüfung nach Checkliste Anwalt. Keine Rechtsberatung. Vor Großkunden / Enterprise: echten Anwalt gegenlesen lassen.

## Ampel
Gesamt: 🟡  
Kurz: Für kleine/mittlere B2B-Kunden brauchbar und klar. Für große Firmen mit Vendor Assessment fehlen TOMs-Tiefe, Löschfristen, Betroffenenrechte und ein paar Haftungs-/Mängel-Klauseln.

---

## Findings

| # | Schwere | Durchgang | Stelle | Problem | Empfehlung |
|---|---------|-----------|--------|---------|------------|
| 1 | hoch | B | AVV TOMs | TOMs nur Stichworte (Zugang, TLS, Backup…). Enterprise-Fragebögen erwarten konkrete Maßnahmen. | TOMs-Anlage 1–2 Seiten: Hetzner Nürnberg, TLS, Zugang 2FA/YubiKey-Admin, Backup-Rhythmus, Log-Retention, Verschlüsselung at rest soweit vorhanden. |
| 2 | hoch | B | AVV Ende | Keine klare Löschung/Rückgabe nach Vertragsende (nur „Datenexport“ in AGB). | AVV-Klausel: Export auf Wunsch, Löschung binnen X Tagen nach Ende, Backup-Ausnahme kurz benennen. |
| 3 | hoch | B | AVV | Betroffenenrechte / Unterstützung bei Auskunft fehlen. | Kurzer Absatz Art. 28 Abs. 3 lit. e: Unterstützung bei Betroffenenanfragen. |
| 4 | mittel | B | AVV Unteraufträge | Änderungen „werden mitgeteilt“, aber kein Widerspruchsrecht des Kunden. | Mitteilung + angemessene Widerspruchsfrist (üblich in AVVs). |
| 5 | mittel | A | AGB Haftung | Deckel 12 Monate Nettovergütung ok. Indirekte Schäden / entgangener Gewinn nicht ausdrücklich. Drittanbieter-Inhalte/Fehler (API-Daten) nicht klar. | Satz ergänzen: keine Haftung für indirekte Schäden soweit zulässig; keine Haftung für Fehler/Ausfälle Dritter-APIs außerhalb Einflussbereich. |
| 6 | mittel | A | Auftrag/AGB | Keine Mängel/Nacherfüllungsfristen. | Kurzer §: Mängel unverzüglich melden, Nacherfüllung in angemessener Frist, sonst Minderung. |
| 7 | mittel | A | AGB | Keine Freistellung bei rechtswidrigen Kundeninhalten / Weisungen. | Freistellungsklausel (Kunde stellt frei bei Ansprüchen aus seinen Inhalten/Weisungen). |
| 8 | mittel | C | Auftrag/AGB | Preisanpassung fehlt. Nach 12 Monaten oft nötig. | Option: Anpassung mit 6–8 Wochen Ankündigung + Sonderkündigung. |
| 9 | niedrig | C | Laufzeit | Verlängerung nach Mindestlaufzeit implizit, nicht als Auto-Verlängerung benannt. | Ein Satz: „verlängert sich auf unbestimmte Zeit, kündbar mit 1 Monat…“ |
| 10 | niedrig | D | Geheimhaltung | „auch nach Ende“, aber ohne Dauer/gesetzliche Ausnahmen. | Dauer z. B. 3 Jahre + Ausnahme gesetzliche Pflichten / bekannte Infos. |
| 11 | niedrig | D | IP | Frameworks bleiben Webschmiede, Kundeninstanz Laufzeit. Kundeneigene Inhalte / erstellte Texte unklar. | Klarstellen: Kundeninhalte bleiben Kunde; gelieferte kundenspezifische Assets nach Zahlung nutzbar wie vereinbart. |
| 12 | ok-Hinweis | D | Leistung | Umfang „laut Angebot“ – ohne ausgefülltes Angebot dünn. | Immer Angebot als Anlage mitsenden (DocuSeal-Flow). |
| 13 | ok-Hinweis | B | Standort | „Hetzner DE/EU“ passt zu Nürnberg-CX43. | Optional „Rechenzentrum Deutschland (z. B. Nürnberg)“ schreiben, wirkt stark im Pitch. |

---

## Checkliste

### A – Haftung & Risiko
| ID | Status | Notiz |
|----|--------|-------|
| A1 | ✅ | AGB: Deckel max. Nettovergütung letzte 12 Monate |
| A2 | ⚠️ | Indirekte Schäden / entgangener Gewinn nicht explizit |
| A3 | ✅ | Vorsatz / grobe Fahrlässigkeit / Personenschäden unbeschränkt |
| A4 | ⚠️ | Drittanbieter nur bei Verfügbarkeit, nicht bei API-Datenfehlern |
| A5 | ❌ | Keine Mängel-/Nacherfüllungsregel |
| A6 | ⚠️ | Datenschutz-Endkunde beim Kunden; keine echte Freistellung Inhalte |
| A7 | n.a. | Keine Versicherungsangabe (ok) |

### B – Datenschutz & AVV
| ID | Status | Notiz |
|----|--------|-------|
| B1 | ✅ | Separater AVV Art. 28 |
| B2 | ⚠️ | Gegenstand/Datenarten ok; Verarbeitungsdauer dünn |
| B3 | ⚠️ | TOMs zu knapp für Enterprise |
| B4 | ✅ | Hetzner DE/EU |
| B5 | ⚠️ | Liste gut; Widerspruch bei Wechsel fehlt |
| B6 | ❌ | Löschung nach Ende nicht geregelt |
| B7 | ✅ | WhatsApp/SMS nur „soweit gebucht“ |
| B8 | ❌ | Betroffenenrechte fehlen |

### C – Geld & Vertragslauf
| ID | Status | Notiz |
|----|--------|-------|
| C1 | ✅ | Setup + Monat netto + USt |
| C2 | ⚠️ | 14 Tage; Verzug/Aussetzung nach Mahnung; Zinsen nicht detailiert |
| C3 | ✅ | Mindestlaufzeit + Kündigungsfrist |
| C4 | ⚠️ | Verlängerung implizit, nicht ausgeschrieben |
| C5 | ❌ | Keine Preisanpassung |
| C6 | ✅ | Aussetzung nach Mahnung |
| C7 | ⚠️ | Fremdkosten/Extras nur grob |

### D – Leistung & Formalia
| ID | Status | Notiz |
|----|--------|-------|
| D1 | ⚠️ | Konkret nur mit Angebot-Anlage |
| D2 | ✅ | Mitwirkung klar |
| D3 | ✅ | Kein Fake-SLA; keine 100 %-Verfügbarkeit |
| D4 | ⚠️ | Frameworks klar; Kundeneigene Assets etwas unscharf |
| D5 | ⚠️ | Geheimhaltung ohne Dauer |
| D6 | ✅ | Auftrag → AGB → AVV stimmig, keine harten Widersprüche |
| D7 | ✅ | Parteien-/Signaturfelder vorhanden |
| D8 | ✅ | DE-Recht, Gerichtsstand Sitz AN |
| D9 | ✅ | AGB + AVV referenziert; Paket-Flow DocuSeal |

### Fremdvertrag F1–F5
n.a. (eigene Vorlagen)

---

## Ampel (nach AGB-Nachschärfung 2026-07-19)
Gesamtpaket Auftrag+AGB+AVV: 🟢 für typisches B2B (Vorprüfung).  
Vor Enterprise weiterhin: echter Anwalt gegenlesen.

AGB ergänzt: Freistellung Inhalte, Preisanpassung + Sonderkündigung, Mängel/Nacherfüllung,
indirekte Schäden + Drittanbieter-APIs, Geheimhaltung 3 Jahre, IP Kundenassets klarer.
Auftrag: Verlängerung nach Mindestlaufzeit ausgeschrieben.
AVV: wie zuvor (TOMs, 30-Tage-Löschung, Betroffenenrechte).

## Nächster Schritt (eine Sache)
Optional Art. 30 Verarbeitungsverzeichnis. Sonst fertig für normale Kundenverträge.
