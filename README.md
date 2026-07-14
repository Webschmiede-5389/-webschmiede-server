# Webschmiede Server

Agency stack for **Digital Craftsmanship** — first client: Snack House Yassine (SHY001).

## Stack

- Flask API + SQLite CRM
- Order portal + admin dashboard
- Jarvis WhatsApp bot
- n8n automation hub
- Hetzner deploy via `deploy.py`

## Quick start

```bash
copy deploy.secrets.local.example deploy.secrets.local   # Windows
pip install paramiko python-dotenv flask flask-cors requests
python deploy.py
```

See `AGENTS.md` and `docs/webschmiede-vision.md` for full playbook.

## GitHub

See `docs/GITHUB.md`.
