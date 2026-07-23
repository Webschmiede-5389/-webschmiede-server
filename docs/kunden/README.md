# Kunden-Übergabe

**Kunden-ID:** siehe [KUNDEN-ID.md](KUNDEN-ID.md) (Format `SHY001`, Branchen-Prefixe, Lead vs. Kunde).

Pro Kunde liegen hier die **Übergabe-Dokumente** für den Inhaber.

## Dateien pro Kunde

| Datei | Zweck |
|-------|--------|
| `SHY001-uebergabe-handout.html` | Druck/PDF fürs Kunden-Meeting (Handbuch) |
| `SHY001-verkaufsblatt.html` | **1 Seite Wert/ROI** — für Gespräch & WhatsApp |
| `SHY001-uebergabe-handout.md` | Bearbeitbare Vorlage (intern) |
| `SHY001-go-live.md` | Call-Skript Testphase (intern) |

**Neuer Kunde:** `SHY00X-uebergabe-handout.html` von SHY001 kopieren und anpassen.

**Onboarding-Portal (live):** `https://[subdomain].digitalehandwerkskunst.de/onboarding?k=SHY00X` — Links, Checkliste, Go-Live-Fortschritt (Daten aus `kunden/*.json` + Server-Status).

**Gastro-Standard:** Tischaufsteller (QR Bestellen + Google) im Onboarding, CI aus `brand` in der Kunden-JSON. Siehe `docs/agency/tischaufsteller-standard.md`.

## PDF erzeugen

1. `SHY00X-uebergabe-handout.html` im Browser öffnen  
2. Drucken → **Als PDF speichern**  
3. Optional: PDF per WhatsApp an Kunden

## Online + E-Mail (automatisch)

```bash
# Handbuch auf Server + Onboarding-Mail
python jarvis.py onboard SHY001 --upload-handout --support-email deine@email.de
```

- Handbuch landet unter: `https://[domain]/uebergabe-handbuch.html`
- E-Mail geht an `kontakt.email` in `kunden/SHY001_….json`
- **Admin-Passwort nie in der Mail** — nur WhatsApp/Telefon

## Vor Übergabe anpassen

- [ ] Support-E-Mail/Telefon im HTML-Footer
- [ ] Links (Test vs. Live-Domain) in `kunden/*.json`
- [ ] Offene Punkte & Upsell-Preise (optional)
- [ ] `python jarvis.py onboard … --dry-run` testen
