# Go-Live mit Hassan Yassine (SHY001)

> **Dauer:** ca. 30–45 Min. · Du führst, Hassan klickt mit.

## Vor dem Termin (du)

```bash
python scripts/go_live.py SHY001 check
python scripts/go_live.py SHY001 configure --owner-phone +49... --sms-key DEIN_SEVEN_KEY --review-url https://g.page/r/...
python deploy.py
```

n8n: `workflow-new-order-alert.json` importieren → Workflow aktivieren → Webhook-URL:

```bash
python scripts/go_live.py SHY001 configure --n8n-webhook http://127.0.0.1:5678/webhook/new-order-shy001
```

## Ablauf im Call

### 1. Begrüßung (2 Min.)
- „Ich zeige dir kurz, was du hast — danach machen wir zusammen zwei Testbestellungen.“
- Onboarding-Mail schon gesendet? Sonst jetzt:
  ```bash
  python scripts/go_live.py SHY001 onboard --upload-handout --support-email DEINE@EMAIL.de
  ```

### 2. Links zeigen (5 Min.)
| Seite | URL |
|-------|-----|
| Website | http://167.233.211.170/ |
| Bestellen | /bestellen |
| Admin | /admin |
| Handbuch | /uebergabe-handbuch.html |

**Admin-Passwort:** per WhatsApp — nicht im Call vorlesen, wenn unsicher.

### 3. Admin-Demo (10 Min.)
1. **Anruf-SMS zeigen** — grüne Leiste: Nummer eingeben → „Bestelllink per SMS“ (Kunde bestellt dann online)
2. Tab **Bestellungen** — Filter, Ton
2. **Online/Offline** — kurz auf Offline, dann wieder Online
3. Tab **Speisekarte** — einen Artikel kurz „ausverkauft“, dann wieder an
4. **Tagesbericht** — Button oben
5. Tab **Kunden** — Review-Link (falls noch leer, gemeinsam eintragen)

### 4. Testbestellungen (10 Min.)

**Option A — du startest remote:**
```bash
python scripts/go_live.py SHY001 test-orders
```

**Option B — Hassan bestellt selbst** auf dem Handy (Abholung + Lieferung).

Dann im Admin:
- Status durchklicken: Neu → Zubereitung → Abholbereit/Fertig
- Optional Bon drucken testen

### 5. SMS & Review (5 Min.)
- Wenn SMS aktiv: „Du solltest eine SMS bekommen haben.“
- Review-Link im Tab Kunden erklären: „3 Tage nach Fertig schickt das System automatisch eine Bewertungsanfrage.“

### 6. Abschluss (5 Min.)
- Go-Live Checkliste aus Handout durchgehen
- „Bei Fragen: WhatsApp an mich.“
- Optional Upsell: Domain, Fotos — **nicht** am ersten Tag drängen

## Nach dem Termin (du)

```bash
python scripts/go_live.py SHY001 check
```

- [ ] Testorders auf „Fertig“ oder löschen (manuell im Admin)
- [ ] `kunden/SHY001_snackhouse.json` → `"status": "live"` wenn freigegeben
- [ ] Kurze WhatsApp: „Alles läuft — melde dich bei Fragen“

## Troubleshooting

| Problem | Lösung |
|---------|--------|
| Keine SMS | `check` → SMS_KEY + OWNER_PHONE + seven.io Guthaben |
| Bestellung Fehler Preis | `extract_menu_catalog.py` + deploy |
| Admin lädt nicht | `systemctl status snack-api` auf Server |
| Kein Ton | Browser: Benachrichtigungen erlauben |
