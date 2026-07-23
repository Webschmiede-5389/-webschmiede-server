# Domains im Kunden-Onboarding

Produktablauf für Webschmiede. Kauf nur nach Kundenklick bzw. nach ausdrücklicher Freigabe durch Christian.

## Prinzip

1. Setup und Onboarding zuerst fertigstellen.
2. Domain-Auswahl erst im Onboarding.
3. Vorschläge vorbereiten und Verfügbarkeit prüfen.
4. Kaufen und umstellen **nur**, wenn der Kunde eine Domain bestätigt.
5. Agent/System kauft nichts „nebenbei“ ohne Freigabe.

## Onboarding-UI (Soll)

### Domain-Auswahl

- Link/Seite im Onboarding mit mehreren Domain-Vorschlägen (Marke, Ort, Varianten).
- Kunde sieht Status (frei / belegt) wo möglich.
- Klick auf eine freie Domain = Bestellung auslösen.

### Wunschdomain

- Freitextfeld „Wunschdomain“ (z. B. `snackhouse-yassine.de`).
- Sofort-Check (RDAP / Registrar-API je nach TLD).
- Wenn **frei**: in Auswahl aufnehmen oder direkt bestätigbar.
- Wenn **belegt**: automatische E-Mail an den Kunden:
  - Kurz: Die Wunschdomain ist nicht frei.
  - Darunter: 3–5 freie Alternativen.
  - Link zurück zur Domain-Auswahl im Onboarding.

## Nach Kunden-Bestätigung (automatisch)

1. Domain registrieren (Cloudflare Registrar wo TLD unterstützt; sonst Provider für `.de`).
2. Zone/DNS bei Cloudflare anlegen, auf Hetzner/Server zeigen.
3. SSL, Nginx/Kunden-Host, URLs in `kunden/*.json` und Onboarding speichern.
4. Kunde und Christian kurz informieren (Domain live / nächster Schritt).

## Kauf-Sperre für Agenten

Ohne ausdrückliche Anweisung von Christian: **kein** Registrar-Kauf, keine kostenpflichtige Buchung. Nur prüfen, vorschlagen, vorbereiten.

## Technik-Hinweis (Stand)

| Thema | Status |
|-------|--------|
| Cloudflare DNS / Zones | optional, nicht mehr Hauptweg |
| Cloudflare Registrar API | kein `.de` |
| **INWX** Domains + DNS | **Hauptweg** — `docs/agency/inwx-domains.md` |
| `.de` kaufen | über INWX API (`integrations/inwx.py`) |
| Onboarding Domain-UI + Wunschdomain-Check | **live** (`onboarding.html`, `domain_onboarding.py`) |
| Mail bei belegter Wunschdomain | **live** (Alternativen + Link zurück) |
| Auto-Kauf bei Kundenklick | Code da, Standard **aus** (`DOMAIN_AUTO_PURCHASE=1`). Braucht INWX Secrets |

### API

- `GET /api/onboarding/<kid>/domains`
- `POST /api/onboarding/<kid>/domains/check` `{ "domain": "…" }`
- `POST /api/onboarding/<kid>/domains/select` `{ "domain": "…" }`

Kunden-JSON: Block `domain.options` (Liste), `domain.selected`, `domain.wish`.

## Verwandt

- INWX Setup: `docs/agency/inwx-domains.md`
- DNS manuell (Agentur): `docs/agency/ionos-dns.md`
- Onboarding-Portal: `docs/kunden/README.md`
- Cursor-Regel: `.cursor/rules/domains-onboarding.mdc`
