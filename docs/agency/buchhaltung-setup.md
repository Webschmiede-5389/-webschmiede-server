# Buchhaltungs-Vorbereitung — Setup

## Meta-Werbung (Karte, keine Rechnungs-Mail)

Meta bietet bei Kartenabbuchung **kein Feld für Rechnungs-E-Mail**. Zwei Wege:

### A) Buchhaltung als Person (einfach)

1. [business.facebook.com](https://business.facebook.com) → **Einstellungen** → **Personen**
2. **Person hinzufügen** → Mail der Buchhaltung
3. Rolle: **Finanz-Analyst** (nur Rechnungen lesen)
4. Optional: nur ein Werbekonto freigeben

Rechnungen: **Abrechnung und Zahlungen** → **Transaktionsverlauf** oder **Rechnungsdokumente**

### B) n8n Weiterleitung (wenn Meta doch mailt)

Workflow: `infra/n8n/workflow-meta-rechnungen.json`

n8n Variables (Agency):

| Variable | Beispiel |
|----------|----------|
| `AGENCY_FROM_EMAIL` | info@digitalehandwerkskunst.de |

**Kunden-Buchhaltung:** `buchhaltung.bookkeeper_email` in `kunden/SHY001_….json`, nicht global in n8n.
Siehe [KUNDEN-ID.md](../kunden/KUNDEN-ID.md).

IMAP-Credential auf Postfach des Kunden (z. B. `rechnungen@…`), falls Meta Monatsrechnung per Mail schickt.

---

## Portal-Umsätze (Gastro z. B. SHY001)

### API (Admin-Passwort)

| Endpoint | Zweck |
|----------|--------|
| `GET /api/admin/report/month` | Monatsumsatz, Bar/EC getrennt |
| `GET /api/admin/export/orders.csv?year=2026&month=7` | CSV für Steuerberater/DATEV-Vorbereitung |

Ohne Parameter: **Vormonat**.

### n8n Monats-Mail

Workflow: `infra/n8n/workflow-buchhaltung-monat.json`

- Läuft am **1. um 07:00**
- Variables: `ADMIN_PASSWORD`, `AGENCY_FROM_EMAIL` (+ pro Kunde `buchhaltung.bookkeeper_email` in JSON)
- Einrichten: `python scripts/setup_n8n_buchhaltung.py`

---

## Checkliste neuer Kunde

- [ ] Buchhaltungs-Mail vom Kunden
- [ ] Meta: Finanz-Analyst eingeladen **oder** Monatsrechnung + Mail-Feld
- [ ] n8n: `workflow-meta-rechnungen.json` (Meta) + `workflow-buchhaltung-monat.json` (Portal)
- [ ] `buchhaltung.bookkeeper_email` in `kunden/SHY00X_….json`
- [ ] n8n: Kunden-Workflows mit ID-Suffix (z. B. `new-order-shy001`)
- [ ] Optional: `rechnungen@kunde.de` → IMAP in n8n

---

## Handwerk / Maler (`PORTAL_MODE=handwerk`)

In `/root/app/backend/.env`:

```
PORTAL_MODE=handwerk
```

Dann:

- Admin: Tab **Anfragen** (Status, Betrag, Bar/EC)
- Kundenformular: `/anfrage.html`
- Monats-CSV: Admin-Button oder `GET /api/admin/export/orders.csv` (Datei `jobs_YYYY-MM.csv`)

API: `POST /api/anfrage`, `GET/PATCH /api/admin/jobs`
