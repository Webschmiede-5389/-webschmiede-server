# CRM Login Migration (Pilot)

**Unverändert:** `/login` POST, Session, CSRF, Passwort-Hash, Rate-Limit, Redirect, Rollen.

**Geändert (nur Markup/CSS):** `app/templates/auth/login.html`

## Zieldarstellung

- Heller Hintergrund (`auth-wrap`)
- Zentrierte Card
- Offizielles `logo-mark.png`
- WebSchmiede / Digitale Handwerkskunst
- Überschrift „CRM anmelden“
- Primary Button Orange `#FF6600`
- Labels sichtbar (`for`/`id`)
- Staging-Badge wenn `APP_ENV` ≠ production
- Kein generisches „W“ / „A“-Buchstabenlogo

## Checks

| Fall | Status |
|------|--------|
| Login 200 lokal | OK (TestClient) |
| CSRF hidden field wenn gesetzt | unverändert |
| Enter submit | native form |
| Passwort in Logs | unverändert (kein neues Logging) |
