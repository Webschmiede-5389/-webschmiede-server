# Webschmiede Server – Agent Guide

This repo is the **agency infrastructure** for Webschmiede (Digital Craftsmanship). First live client: **Snack House Yassine (SHY001)**.

## Quick commands

```bash
python jarvis.py kunden          # list clients
python jarvis.py kunde SHY001    # client details
python jarvis.py neu             # new client wizard
python deploy.py                 # deploy to server
python setup_crm_env.py          # CRM/SMS env on server
python setup_n8n.py              # n8n automation hub on server
```

## n8n (Automation Hub)

- **URL:** http://167.233.211.170/n8n/
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
5. **Design:** Match existing dark/gold Snack House style; avoid generic AI aesthetics.
6. **Scope:** Minimal diffs; don't refactor unrelated code.

## Cursor skill

Full playbook for future projects: personal skill **`webschmiede-os`**  
(`~/.cursor/skills/webschmiede-os/SKILL.md` + `reference.md`)

## Status (July 2026)

### Done
- Order portal + admin dashboard (orders, promos, menu, printer, reports, push)
- Own CRM (`contacts`, `message_log`, Kunden tab)
- SMS automation ready (seven.io, needs API key)
- GHL disabled on server
- DSGVO pages, security headers, favicons
- Agency CLI + kunden.json

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
  - **Trend Scout:** global market scan → knowledge DB → weekly DE-fit reports → niche recommendations
  - **Social Pipeline (German Golf Guide):** n8n + Meta API — copy, design, schedule IG/FB; own comments only; no auto-engagement on third-party profiles — see vision doc
