# Webschmiede Server – Agent Guide

This repo is the **agency infrastructure** for Webschmiede (Digital Craftsmanship). First live client: **Snack House Yassine (SHY001)**.

## Quick commands

```bash
python jarvis.py kunden          # list clients
python jarvis.py kunde SHY001    # client details
python jarvis.py neu             # new client wizard
python deploy.py                 # deploy to server (needs deploy.secrets.local)
python setup_crm_env.py          # CRM/SMS env on server
python setup_n8n.py              # n8n automation hub on server
```

## Cursor Cloud specific instructions

Local Cloud Agent / VM without production deploy:

```bash
bash scripts/cloud-agent-install.sh   # venv + pip + agency-web npm (idempotent)
bash scripts/cloud-agent-start.sh     # API :8000 + static :8080
```

- API health: `curl -s http://127.0.0.1:8000/api/health`
- Order portal UI: `http://127.0.0.1:8080/order.html`; admin: `http://127.0.0.1:8080/admin.html`
- Dev admin password in generated `app/backend/.env`: `dev-local-pass` (local only)
- Admin API auth: `X-Admin-Token` after `POST /api/admin/login`
- Do **not** run `python deploy.py` or publish `agency-web` unless Christian explicitly asks
- Production secrets stay in `deploy.secrets.local` (gitignored); Cloud Agents use local `.env` stubs

**GitHub:** Repo initialized locally. Push: see `docs/GITHUB.md`. Secrets in `deploy.secrets.local` (gitignored).

## n8n (Automation Hub)

- **URL:** https://digitalehandwerkskunst.de/n8n/
- **Login:** see `n8n-credentials.local.txt` (local only, gitignored)
- **Workflow templates:** `infra/n8n/*.json` — import in n8n UI
- **Docs:** `infra/n8n/README.md`

## Stack

- **Frontend:** Static HTML (Tailwind CDN, Font Awesome, Bunny Fonts)
- **Backend:** Flask + SQLite (`app/backend/main.py`)
- **Server:** Nginx + systemd `snack-api` on port 8000
- **CRM:** Own `contacts` table – **not GoHighLevel** (`GHL_ENABLED=false`)
- **SMS:** seven.io (`SMS_ENABLED` in `.env`)

## Key files

| File | Purpose |
|------|---------|
| `app/static/order.html` | Customer order portal |
| `app/static/admin.html` | Client operations dashboard |
| `app/static/index.html` | Marketing website |
| `app/backend/main.py` | API, CRM, SMS, promos |
| `kunden/*.json` | Per-client config |
| `jarvis.py` | Agency CLI |
| `deploy.py` | Deployment |
| `app/backend/.env.example` | Required environment variables |

## Rules for agents

1. **German** responses to the user unless they use another language.
2. **No GHL** for new features – extend own CRM/SMS.
3. **DSGVO:** Bunny Fonts, no tracking, document third parties in `datenschutz.html`.
4. **Deploy:** Always run `deploy.py` after static/backend changes; verify `snack-api` active.
5. **Design:** Match existing dark/gold Snack House style; avoid generic AI aesthetics. Agency wordmark: only freigestelltes `/ci/webschmiede-logo.png` (see `docs/agency/ci/BRAND.md`).
6. **Scope:** Minimal diffs; don't refactor unrelated code.
7. **Ton:** Kunden-Texte und Mails menschlich, kein KI-Marketing — siehe `.cursor/rules/menschlicher-ton.mdc`.
8. **Betriebssicherheit:** Alles muss 24/7 zuverlässig laufen — Fehler früh erkennen, auto-reparieren, Inhaber informieren. Kunde ist nie First-Line-Support. Siehe `.cursor/rules/betriebssicherheit.mdc` (Smoke-Tests, Watchdog, klare Fehlermeldungen, kein stilles Scheitern).
9. **Gedächtnis:** Beschlüsse und aktueller Fokus in `docs/memory/` schreiben. Bei Chat-Überlast Handoff füllen und neuen Chat vorschlagen (Rule `wissen-und-chats.mdc`).
9. **Nils:** Ops-Mitarbeiter (KI), unter Stefan. Regel `.cursor/rules/nils.mdc`, Skill `.cursor/skills/nils/`, Handbuch `docs/agency/nils.md`.
10. **Stefan:** Betriebsleiter (KI). Tempo und Priorität. Regel `.cursor/rules/stefan.mdc`, Sheet `docs/agency/stefan.md`.

## Cursor skill

Full playbook for future projects: personal skill **`webschmiede-os`**  
(`~/.cursor/skills/webschmiede-os/SKILL.md` + `reference.md`)

**Multi-project workflow:** see `docs/webschmiede-workspace.md` (which folder, which chat, GitHub).

**Direction (start here):** `docs/DIRECTION.md` — folder map, commands, customer lifecycle, onboarding mail.

**Agency invoices (no sevDesk yet):** `docs/agency/rechnung-vorlage.html` · `docs/agency/angebot-vorlage.html`

## Status (July 2026)

### Done
- Order portal + admin dashboard (orders, promos, menu, printer, reports, push)
- Own CRM (`contacts`, `message_log`, Kunden tab)
- SMS automation ready (seven.io, needs API key)
- GHL disabled on server
- DSGVO pages, security headers, favicons
- Agency CLI + kunden.json
- **Stellenplan / Team-Radar:** `docs/agency/mitarbeiter-stellenplan.md`, `docs/agency/trend-scout.md`

### Planned
- Agency browser dashboard (jarvis web UI)
- PWA, loyalty, review funnel, WhatsApp promo control
- **Product vision (hub + niches):** see [`docs/webschmiede-vision.md`](docs/webschmiede-vision.md)
 - Sales wizard + forecast portal
 - Acquisition scanner (Akquise-Krieger) per vertical
 - Industry landings (`/gastro`, `/dach`, …) + separate Instagram per niche
 - Auto-onboarding after Stripe
 - Instagram post pipeline (approval queue)
 - FlyRuwe-style hub: one webschmiede.de, many industry spokes
 - **Trend Scout:** weekly DE-fit reports → niche recommendations (`docs/agency/trend-scout.md`)
 - **Social Pipeline (German Golf Guide):** n8n + Meta API — copy, design, schedule IG/FB; own comments only; no auto-engagement on third-party profiles — see vision doc


## Webschmiede-Standard: fester Umfang und sichtbare Abnahme

**Verbindlich ab 05.10.2026 für jeden Auftrag und jedes Projekt.**

Jeder Auftrag braucht vor Implementierung einen festen Umfang und einen vollständigen, sichtbaren Abnahmelauf. Festhalten: Nutzer/Ziel, Must-have, Out-of-Scope, sichtbarer Einstieg, Ablauf bis zum fachlichen Ergebnis, relevante Fehler-/Abbruchpfade und prüfbare Abschlusskriterien. Bei Aufgaben ohne UI ist der Nachweis das tatsächlich nutzbare Ergebnis im passenden Medium; keine künstliche Oberfläche bauen.

Den Umfang nicht still auf Foundation, Labels, APIs oder einen kleineren Slice reduzieren. Zusammenhängende autorisierte Arbeit bis zu den vereinbarten Kriterien ausführen; interne Schritte brauchen keine wiederholte Freigabe. Echte Blocker und Umfangsänderungen ausdrücklich benennen. Kein PASS bei fehlender Kernfunktion oder fehlendem gefordertem Nachweis.

Bei UI-Aufträgen auf der tatsächlich geöffneten URL prüfen: Port, Projektprozess, Arbeitsverzeichnis, Branch/Commit und lokale Änderungen dokumentieren. Ein anderer QA-Port beweist nicht den Nutzerstand. Sichtbare Navigation bis zum fachlichen Ergebnis testen, einschließlich passender Rollen, Geräte und Fehlerpfade. Eine Erfolgsmeldung ohne verarbeitetes Ergebnis ist kein Nachweis. Bestehende Daten erhalten und keine fremden Prozesse pauschal beenden.

Implementierung, ausgeführte Tests, vollständige Browserabnahme, externes Review, echter Nutzertest und Demo-/Live-Freigaben getrennt berichten. Screenshots/Aufnahmen und Dokumentation dem geprüften Stand zuordnen. Synthetischer PASS ersetzt keinen echten Nutzer.

Dieser Standard gilt auch für neue Projektvorlagen: in die projektspezifischen AGENTS-/Cursor-Regeln übernehmen und im Auftrag konkretisieren. Vorhandene Freigabegrenzen bleiben erhalten; die Regel autorisiert keinen Merge, Deploy, Versand oder Live-Zugriff. Offene Human-/Review-Abnahme blockiert nicht automatisch weitere reversible, bereits autorisierte Arbeit.
