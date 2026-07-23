# Auth: Sessions, Users, Reset, 2FA

Stand: 2026-07-20

## Live

- Agency-Login: `POST /api/agency/login` → Session-Token + Cookie `agency_session`
- Header: `X-Agency-Token` (UI). Legacy `X-Agency-Password` noch für Scripts (`AGENCY_ALLOW_PASSWORD_HEADER=1`)
- Users in SQLite (`portal_users`), Passwort gehasht (Werkzeug)
- Bootstrap-User `christian` aus `AGENCY_ADMIN_PASSWORD` beim Start
- Passwort vergessen: `POST /api/auth/forgot` + `POST /api/auth/reset` (SMTP Agency)
- 2FA TOTP: Setup `/api/agency/2fa/setup` + confirm (pyotp)
- Kunden-Admin: Login mit User `admin` oder Legacy-Passwort, Session in DB

## Dateien

- `app/backend/auth_users.py`
- `app/backend/main.py`
- `app/static/agency-auth.js`
- Agency-HTMLs nutzen Token statt Klartext-PW

## Offen

- YubiKey / WebAuthn
- 2FA in UI als Wizard-Seite (API schon da)
- `AGENCY_ALLOW_PASSWORD_HEADER=0` wenn n8n umgestellt
