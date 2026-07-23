# IONOS → Hetzner: digitalehandwerkskunst.de

> Agency-Website liegt auf dem Server unter `/var/www/digitalehandwerkskunst`.

---

## Schritt 1 — IONOS DNS ändern

1. [ionos.de](https://www.ionos.de) → **Domains & SSL**
2. `digitalehandwerkskunst.de` → ⚙️ → **DNS**

### Entfernen (Replit)

- **A-Record** mit alter Replit-IP
- **TXT** mit `replit-verify=...` (nur noch nötig bei Replit-Hosting)

**MX-Records für E-Mail nicht anfassen.**

### Hinzufügen / ändern

| Typ | Hostname | Wert |
|-----|----------|------|
| **A** | `@` | `167.233.150.230` |
| **A** | `www` | `167.233.150.230` |

Speichern. Propagation: 5 Min. bis 48 Std.

### Kunden-Subdomains

| Typ | Hostname | Wert | Zweck |
|-----|----------|------|--------|
| **A** | `muster` | `167.233.150.230` | **Demo für alle** (Verkauf, Muster) |
| **A** | `yassine` | `167.233.150.230` | Snack House Yassine (Test) |

Weitere Kunden beim Onboarding: z. B. `pizzeria-roma` → `python jarvis.py subdomain KUNDENID pizzeria-roma --ssl`

### Wildcard (empfohlen — wie GHL: einmal verbinden, dann automatisch)

| Typ | Hostname | Wert | Effekt |
|-----|----------|------|--------|
| **A** | `*` | `167.233.150.230` | **Jede** Subdomain zeigt auf Hetzner — kein IONOS mehr pro Kunde |

Danach reicht lokal:

```bash
python jarvis.py subdomain SHY001 yassine --ssl
python jarvis.py subdomain NEU001 pizzeria-roma --ssl
```

Nginx + SSL macht Jarvis/Cursor — **ohne** erneutes IONOS-Klicken.

*(Optional später: IONOS Cloud DNS API-Key in `/agency-keys` — nur nötig, wenn du keinen Wildcard nutzt.)*

```bash
python scripts/setup_client_subdomain.py --demo muster --ssl
python scripts/setup_client_subdomain.py SHY001 yassine --ssl
```

---

## Schritt 2 — HTTPS (nach DNS)

Lokal ausführen (wenn Domain auf Hetzner zeigt):

```bash
python setup_agency_nginx.py --ssl
```

---

## Schritt 3 — Test

- https://digitalehandwerkskunst.de/
- Seite = WebSchmiede Handwerk (React), nicht Snack House

**Vor DNS-Umstellung testen:** Seite ist bereits auf dem Server — nur Domain zeigt noch auf Replit.

---

## Updates deployen

Nach Replit-Import + `npm run build`:

```bash
python scripts/deploy_agency.py
```

Oder Backup von Live neu ziehen:

```bash
python scripts/download_agency_static.py
python scripts/deploy_agency.py
```

---

## Server-Architektur

| Domain / IP | Inhalt |
|-------------|--------|
| **digitalehandwerkskunst.de** | Agency-Website (React) |
| **167.233.211.170** (ohne Domain) | Snack House Hassan |
| `/seminare`, `/agency` auf IP | Interne Webschmiede-Tools |
