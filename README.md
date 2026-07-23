# Webschmiede Server

Agency stack for **Digital Craftsmanship** — first client: Snack House Yassine (SHY001).

**Start here:** [`docs/DIRECTION.md`](docs/DIRECTION.md) — Ordner, Befehle, Kunden-Lebenszyklus.

## Quick start

```bash
copy deploy.secrets.local.example deploy.secrets.local   # Windows
pip install paramiko python-dotenv flask flask-cors requests
python deploy.py
python jarvis.py kunden
```

## Docs

| Doc | Inhalt |
|-----|--------|
| [docs/DIRECTION.md](docs/DIRECTION.md) | Kompass (Einstieg) |
| [docs/webschmiede-workspace.md](docs/webschmiede-workspace.md) | Jarvis-Ordner & Cursor-Chats |
| [docs/webschmiede-vision.md](docs/webschmiede-vision.md) | Strategie & Roadmap |
| [docs/kunden/](docs/kunden/) | Übergabe-Handouts |
| [AGENTS.md](AGENTS.md) | Cursor-Agent-Regeln |

## Onboarding Kunde

```bash
python jarvis.py onboard SHY001 --dry-run
python jarvis.py onboard SHY001 --upload-handout --support-email du@webschmiede.de
```

## Go-Live (SMS + Review + Tests + Onboarding)

```bash
python scripts/go_live.py SHY001 check
python scripts/go_live.py SHY001 configure --owner-phone +49... --sms-key KEY --review-url URL
python scripts/go_live.py SHY001 test-orders
python scripts/go_live.py SHY001 run --support-email du@webschmiede.de
```

Call-Skript: `docs/kunden/SHY001-go-live.md`

SMTP: `AGENCY_SMTP_*` in `deploy.secrets.local` (see example file).
