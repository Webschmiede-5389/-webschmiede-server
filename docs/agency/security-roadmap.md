# Sicherheit Dual-Server + Kundenportale

Stand: 2026-07-17  
Server: web-01neu + auto-01neu. Kein dritter Server nötig für Security.

## Schon da

- UFW, fail2ban (SSH)
- HTTPS / Let’s Encrypt
- Rate-Limits in der API
- Security-Header (X-Frame, nosniff, CSP Basis)
- Stripe-Webhook mit Signaturprüfung
- Datenschutz-Seiten, Bunny Fonts
- Watchdogs mit Schränken
- SQLite nicht im Webroot
- Secrets lokal / Server-`.env`, nicht in Git

## Jetzt zuerst (diese Woche)

| # | Was | Warum |
|---|-----|--------|
| 1 | **Hetzner Cloud Firewall** + SSH nur deine IP / Key-Login | API-Token kann Server steuern – Angriffsfläche SSH schließen |
| 2 | **HSTS** in Nginx (alle 443-Hosts) | Browser nur HTTPS |
| 3 | **Backup verschlüsseln** + Offsite aktiv | Kunden-/Bestelldaten, DSGVO, Ausfall |
| 4 | **unattended-upgrades** | Security-Patches ohne manuell |

## Danach (Portale / Alltag)

| # | Was | Warum |
|---|-----|--------|
| 5 | Admin nur Session-Cookie (HttpOnly/Secure), kein Dauer-Passwort im Header | Kunden-Admin härten |
| 6 | Dateirechte `.env` / `orders.db` → 600 | lokale Lesbarkeit begrenzen |
| 7 | CSP ohne `unsafe-eval` wo möglich | XSS-Härte |
| 8 | Log-Retention automatisieren (PII in SMS-Logs) | DSGVO Speicherbegrenzung |

## Finance / DSGVO (Rahmen)

- **DSGVO:** AV-Verträge mit Auftragsverarbeitern (Hetzner, Stripe, seven, Meta, …), Verarbeitungsverzeichnis, Löschkonzept Bestellungen/Kontakte
- **Finance:** Stripe-Webhook signiert lassen; keine offenen Rechnungs-URLs ohne Token; Buchhaltungs-Export nur hinter Admin
- **Hacker:** Firewall + fail2ban + Rate-Limits + Watchdog reichen für Start; kein „Security-Tool-Zoo“ ohne Bedarf

## Bewusst später

- WAF/Cloudflare vor die Domain (optional, nicht Pflicht)
- 2FA für Agency-Admin
- Separater DB-Server (erst bei vielen Kunden)
- Penetrationstest extern (wenn Umsatz/Kunden kritischer)

## Status 2026-07-17 Phase 1+2

Erledigt:
- Hetzner Firewall `webschmiede-dual` (SSH nur Admin-IP)
- HSTS
- Backup AES lokal + **Offsite Storage Box** `webschmiede-backups` (bx11, fsn1)
- unattended-upgrades
- Dateirechte 600
- Admin-Login: Session-Token + HttpOnly-Cookie (kein Passwort mehr im Header)

Admin-IP: `admin-ip.local.txt`  
Skripte: `setup_security_phase1.py`, `setup_storage_box_offsite.py`
