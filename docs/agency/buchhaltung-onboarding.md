# Buchhaltungs-Onboarding (Wizard)

Stand: 2026-07-19

Beim Kunden: Tools wählen → Fragen → Paket-Empfehlung → AVV → Zugänge verschlüsselt.

## Live

- UI: `/buchhaltung-onboarding.html`
- Auch Link im B2B-Portal Tab Buchhaltung
- Schema: `GET /api/buchhaltung/onboarding/schema`

## Ablauf

1. Christian startet Session (Agency-Passwort) → Link mit `id` + `t`
2. Kunde: Firma, Tools, Fragen
3. System empfiehlt Beleg / Sync / Silo (aus `angebote.json`-Stufen)
4. AVV-Haken + Name
5. Erst dann: IMAP App-Passwort, Lexware/sevDesk Keys (keine Hauptpasswörter)
6. Fertig → Mail an dich, Vault verschlüsselt

## Agency

- Liste: `GET /api/buchhaltung/onboarding` (Agency-Auth)
- Export für n8n: `POST /api/buchhaltung/onboarding/<id>/export` (Agency-Auth, Audit-Log)
- Vault-Key: `BUCHHALTUNG_VAULT_KEY` in Secrets (sonst Ableitung aus Admin-PW)

## DSGVO

- Keine Secrets in API-Responses
- AVV Pflicht vor Vault
- Dateien unter `vault/buchhaltung/*.enc` (nicht Webroot)
- n8n-Credentials legt Nils nach Export an, kein Auto-Push

## Noch manuell nach dem Wizard

- n8n-Workflows pro Kunde aktivieren
- Lexware Env `LEXWARE_API_KEY_{KID}`
- DocuSeal Angebot unterschreiben
- Echter AVV-PDF wenn noch nicht unterschrieben
