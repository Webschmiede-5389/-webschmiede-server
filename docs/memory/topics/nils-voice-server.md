# Nils = Stimme zum Server + Cursor-Bridge

Stand: 2026-07-20

## Ziel

Unterwegs per Telegram dasselbe wie Cursor-IDE: Website/App programmieren, Repo ändern.

## Architektur

1. Nils-Tools (Ops, Scrape, Texte, Entwürfe) – lokal auf dem Server
2. **Cursor Cloud Agent** via `nils_cursor_bridge.py` + `cursor-sdk` – echte Code-Arbeit
3. Freigabe per „ja“ vor Start (Cursor-Account-Kosten)
4. Deploy weiter manuell / nach PR-Review (`python deploy.py`)

## Setup (Christian)

1. Cursor Dashboard → Integrations → User API Key
2. `cursor.secrets.local` (oder requesty.secrets.local): `CURSOR_API_KEY=…`
3. GitHub-Repo an Cursor Cloud Agents hängen
4. Auf Server: Datei nach `/root/app/cursor.secrets.local` oder Env, `pip install cursor-sdk`

Telegram: `baue Website …` → Freigabe → Agent. Status: `cursor status`.

## Ohne Key

Workorder-Handoff wie bisher + Hinweis.
