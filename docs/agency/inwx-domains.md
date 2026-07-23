# Domains über INWX (Webschmiede)

Stand: 2026-07-23

> **Soll-Standard (firmenweit):** INWX = Registrar, **DNS/SSL/WAF = Cloudflare**.  
> Canonical: `My_Company_Hub/infrastructure/STANDARDS.md`  
> Der Abschnitt „INWX → Kauf + DNS“ unten ist **Legacy-Formulierung** — Code nutzt bereits Cloudflare als Default (`via_cloudflare=True`).

## Ziel

Du verbindest mich einmal mit der INWX-API. Danach kann ich Domains (inkl. `.de`) kaufen, Nameserver auf Cloudflare setzen und DNS über Cloudflare provisionieren.

```
INWX          → Kauf + NS-Umstellung
Cloudflare    → DNS, WAF, SSL (Standard)
Hetzner web-01 → Origin (WEB_HOST)
```

Legacy-Fallback: Bei Cloudflare-Fehler kann der Server temporär A-Records bei INWX setzen (`integrations/inwx.py`).

## Einmalig bei INWX (du)

1. Account: https://www.inwx.de
2. Guthaben aufladen (für Domain-Käufe)
3. **Kontakt** anlegen (Domains → Kontakte) — Inhaber Webschmiede / Christian
4. Kontakt-**ID** notieren (Zahl)
5. API-Zugang: Benutzername + Passwort (ggf. API-Passwort in den Einstellungen)

In `deploy.secrets.local` bzw. `/agency-setup`:

```
INWX_USER=dein-user
INWX_PASSWORD=dein-passwort
INWX_CONTACT_ID=12345678
WEB_HOST=167.233.150.230
```

Optional Test-API: `INWX_OTE=1`

## Test

```bash
python scripts/provision_domain_inwx.py --test
```

Im Agency-Setup: Gruppe „Domains (INWX)“ → Speichern → Test.

## Domain kaufen + DNS (z. B. Yassine)

Nach Freigabe von Christian:

```bash
python scripts/provision_domain_inwx.py snackhouse-yassine.de
python scripts/provision_domain_inwx.py snackhouse-yassine.de --ssl
```

Nur DNS (Domain schon bei INWX):

```bash
python scripts/provision_domain_inwx.py snackhouse-yassine.de --dns-only --ssl
```

## Auto-Kauf im Onboarding

Standard **aus**. Nur mit `DOMAIN_AUTO_PURCHASE=1` und gesetztem INWX kauft das System nach Kundenklick.

## Code

| Datei | Rolle |
|-------|--------|
| `app/backend/integrations/inwx.py` | DomRobot Client |
| `scripts/provision_domain_inwx.py` | CLI Kauf/DNS/SSL |
| `app/backend/domain_onboarding.py` | Onboarding-Kauf-Pfad |
| Agency Setup | Secrets + Test-Button |

## Nameserver (INWX DNS)

- `ns.inwx.de`
- `ns2.inwx.de`
- `ns3.inwx.eu`

(werden beim Kauf gesetzt)
