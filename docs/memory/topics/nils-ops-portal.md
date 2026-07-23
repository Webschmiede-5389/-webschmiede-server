# Topic: Nils Ops Portal (Web-App)

Stand: 2026-07-17

## URL

`https://digitalehandwerkskunst.de/nils` (nginx-Route in **sites-enabled** + sites-available)

## Fix 2026-07-17

`/nils` zeigte Startseite: SPA `location /` fing ab. Patch `scripts/patch_nils_nginx.py` (role=web, beide nginx-Dateien).

## Funktion

Privates Ops-Portal nur für Christian (Agency-Passwort):

- Text-Chat
- Diktat (Browser Speech API)
- Sprachnachricht halten → Whisper-Transkript
- Bilder/Videos hochladen → Vision-Analyse (OPENAI_API_KEY)
- Briefing → neuer Kunde anlegen (mit Bestätigung)
- Weiter: Jarvis-Befehle (Status, Subdomain, Angebot, …)

## API

| Endpoint | Zweck |
|----------|--------|
| `GET /api/nils/history` | Chat-Verlauf |
| `POST /api/nils/message` | Text |
| `POST /api/nils/upload` | Multipart Medien + Text |
| `GET /api/nils/media/<id>` | Medien abrufen (Auth) |

## Technik

- `app/backend/nils_ops.py`
- `app/static/nils.html`
- Uploads: `uploads/nils_ops/`

## Nächster Schritt

- WhatsApp gleiche Pipeline wenn Meta fertig
- OPENAI_API_KEY muss auf dem Server gesetzt sein (sonst nur Kurzbefehle)

## Fix 2026-07-17 (Abend)

- Persona **Nils** (nicht Jarvis), Chat-Verlauf an LLM
- Messenger-UI, Typing, 120s Client-Timeout, Voice = Tippen statt Halten
- Nginx `proxy_read_timeout 180s` für `/api/nils/`
