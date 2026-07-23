# DSGVO-Check Webschmiede / Digitale Handwerkskunst

Stand: 2026-07-18 (Fact-Check-Korrektur)  
**Keine Rechtsberatung.** Nur belegte Aussagen. Belege: `dsgvo-factcheck.md` + `dsgvo-factcheck-live.json`.

---

## Ampel nach Korrektur

| Bereich | Urteil |
|---------|--------|
| Impressum + Datenschutz Agency | OK (aktualisiert, live) |
| Datenschutz Kunde SHY | OK (Logs 14 Tage, Push, Hetzner, …) |
| Index-Modal | OK (kein GHL/Google Fonts) |
| Kein Analytics-Pixel | OK |
| AVV Unteraufträge | OK erweitert („soweit gebucht/eingesetzt“) |
| anfrage.html | OK Link + Checkbox |
| Onboarding Meta-SDK | OK Hinweis |
| message_log Retention | OK Purge 90 Tage im Nightly |
| Verarbeitungsverzeichnis Art. 30 | **erledigt** (`verarbeitungsverzeichnis-art30.md`) |
| CDN self-host / catbox | mittel, später |

---

## Fact-Check Highlights (Server 18.07.)

- Nginx-Logs: **14 Tage** (nicht 7)
- SMS/WhatsApp/Stripe Endkunde: **nicht live** (Keys fehlen / SMS false)
- Push/VAPID: **gesetzt**, UI vorhanden
- Retell-Key: gesetzt (Voice-Pfad)
- DocuSeal + Cal.com URLs: gesetzt
- GHL: false

---

## Deploy

- Portal/`datenschutz.html`/`anfrage`/`onboarding`/`nightly_watchdog`: via `deploy.py`
- Agency Datenschutz: via Agency-Dist-Upload (HTTP 200 `/datenschutz`)
- AVV: DocuSeal Templates neu

---

## Noch für Anwalt / dich

1. Kurzes Verarbeitungsverzeichnis (Art. 30) – Vorlage können wir bauen
2. Optional CDN/Bilder lokal (weniger Drittland-IP)
3. AVV/AGB vor erstem Großkunden gegenlesen lassen
