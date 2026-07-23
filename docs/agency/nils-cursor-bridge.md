# Agency: Nils Cursor-Bridge (Telegram = Cursor)

Stand: Juli 2026

## Idee

Christian sagt unterwegs zu Nils: baue Website / programmiere Feature.
Nils startet denselben **Cursor Cloud Agent**, den du in der IDE nutzt.

## Voraussetzung

1. User API Key: Cursor Dashboard → Integrations
2. Datei `cursor.secrets.local` (Vorlage: `cursor.secrets.local.example`)
3. Repo `Webschmiede-5389/-webschmiede-server` an Cursor Cloud Agents
4. Server: `pip install cursor-sdk` im snack-api-venv

## Telegram

- `baue Website für …` / `programmiere …` / `cursor: …` → Freigabe „ja“
- `cursor status` / `cursor status cj_…`
- Deploy bleibt bewusst: nach PR `python deploy.py` (oder dein OK)

## Module

- `app/backend/nils_cursor_bridge.py`
- Tool `cursor_code` / `cursor_status` in `nils_tools.py`
