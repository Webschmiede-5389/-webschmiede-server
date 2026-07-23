# Webschmiede Vertragspaket

Stand: 2026-07-18  
Auftraggeber: Christian Kummetat · Webschmiede / Digitale Handwerkskunst · Mechernich  
USt-IdNr.: DE370109681 · Einzelunternehmen · nur B2B

**Hinweis:** Praxisnahe B2B-Vorlagen. **Keine Rechtsberatung.**  
„Wasserdicht“ nur nach Freigabe durch einen zugelassenen Anwalt.  
Briefing zum Gegenlesen: `docs/agency/vertraege/ANWALT-BRIEFING.md`

**KI-Vorprüfung:** Skill `anwalt` („Anwalt, prüfe …“) · Checkliste `.cursor/skills/anwalt/checkliste.md` · Sheet `docs/agency/anwalt.md`

## Live in DocuSeal

Dashboard: https://sign.digitalehandwerkskunst.de/templates  
Ordner: **Webschmiede Verträge**

| Vorlage | Docs | Zweck |
|---------|------|--------|
| WS Kundenpaket Auftrag AGB AVV | 3 | **Standard** für echte Kunden (ein Link) |
| WS Angebot | 1 | optional vor dem Auftrag |
| WS Auftrag / AGB / AVV | je 1 | einzeln, falls nötig |

## Kunden senden (dein Flow)

Du sagst Firma, Preise, Mail. Dann:

```bash
python scripts/send_vertraege_kunde.py ^
  --firma "Snack House Yassine" ^
  --email kunde@example.de ^
  --vertreter "Yassine ..." ^
  --adresse "Strasse 1, PLZ Ort" ^
  --setup 998 --monat 298 --laufzeit 12
```

Was passiert:
1. Prefill: Firma, Adresse, Paket, Setup, Monat, Laufzeit, Daten
2. Deine Unterschrift wird vorausgefüllt (Asset `assets/unterschrift-christian.png`)
3. Ein Kunden-Link (Auftrag → AGB → AVV von oben nach unten)
4. Kunde unterschreibt nur seine Felder

`--no-email` = nur Link ausgeben (wenn DocuSeal-SMTP noch wackelt).  
`--angebot` = nur Angebot statt Paket.  
`--dry-run` = Prefill anzeigen, nichts senden.

Letzter Send: `docs/agency/vertraege/_last_send.json`

## Was wann unterschreiben

```
Interessent
    │
    ├─ 1) ANGEBOT  ──────────────── optional
    │
    └─ 2) KUNDENPAKET ───────────── Auftrag + AGB + AVV (ein Link)
```

## CI

Oben: **weiß** mit Logo + schwarzem Titel, orangene Trennlinie.  
Rest: orange Abschnitte/Footer, Arial.  
Rebuild: `python scripts/restyle_vertraege_ci.py` → `build_vertraege_pdf.py` → `create_vertraege_docuseal_rails.py`

## Dateien

| Pfad | Zweck |
|------|--------|
| `01-…html` … `05-…html` | lesbare HTML |
| `pdf/*.pdf` | AcroForm-PDFs |
| `assets/webschmiede-logo-print.png` | Logo |
| `assets/unterschrift-christian.png` | deine vorausgefüllte Signatur |
| `scripts/send_vertraege_kunde.py` | Kundenpaket senden |

## SMTP

DocuSeal Settings → Email: https://sign.digitalehandwerkskunst.de/settings/email  
Bis Auth sicher ist: Link per WhatsApp/Mail selbst schicken (`--no-email`).

## Kundensicherheit

| Sorge | Dokument |
|-------|----------|
| Preis/Leistung | Angebot + Auftrag |
| Kündigung | Auftrag + AGB |
| Haftung | AGB |
| DSGVO | AVV |
| Betriebsende | AGB (Export, Hosting endet) |
