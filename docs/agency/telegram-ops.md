# Telegram Ops (Christian ↔ Nils)

Stand: 2026-07-19

Interner Kanal, unabhängig von Meta. Kunden bleiben bei WhatsApp.

## Deine Schritte (~10 Min)

### 1. Bot anlegen

1. Telegram öffnen, **@BotFather** suchen  
2. `/newbot`  
3. Name z. B. `Webschmiede Nils`  
4. Username z. B. `webschmiede_nils_bot` (muss auf `_bot` enden)  
5. **Token** kopieren (sieht aus wie `7123456789:AAH…`)

### 2. Bei uns eintragen

Agency-Setup → Messaging / Telegram:

1. `TELEGRAM_BOT_TOKEN` = der Token  
2. Speichern  

Noch **ohne** Chat-ID: erstmal Bot anschreiben.

### 3. Chat-ID holen

1. Deinen neuen Bot in Telegram öffnen  
2. `/start` oder `Hallo` schreiben  
3. Antwort von Nils: **Deine Chat-ID ist: …**  
4. Diese Zahl als `TELEGRAM_OWNER_CHAT_ID` in Agency-Setup eintragen  
5. Speichern  

Optional mehrere: `TELEGRAM_OWNER_CHAT_IDS` Komma-getrennt.

### 4. Webhook setzen

Auf dem Server / lokal mit Secrets:

```bash
python scripts/setup_telegram_webhook.py
```

Oder API (Agency-Auth): `POST /api/telegram/setup-webhook`

Webhook-URL: `https://digitalehandwerkskunst.de/api/telegram/webhook`

Optional: `TELEGRAM_WEBHOOK_SECRET` (beliebiges Geheimnis) – Telegram schickt es im Header `X-Telegram-Bot-Api-Secret-Token`.

### 5. Test

An den Bot:

```
Nils Status
```

Erwartung: kurze Ops-Antwort. Funnel-Pings (Freigabe, Einladung, …) kommen danach auch hier an.

## Freies Schreiben

Standard: **Ollama** `qwen2.5:14b` auf auto-01 (gratis, CPU, kein API-Geld).  
web-01 ruft `http://AUTO_HOST:11434` auf. Wetter/Suche gratis über Open-Meteo + DuckDuckGo.  
Sprachnachrichten: Whisper am Voice-Gateway `http://AUTO_HOST:8090/api/stt`.

Für ChatGPT-/Grok-Niveau (bezahlt, nur nach OK): Key in Agency-Setup und `LLM_PROVIDER=cloud`  
(OpenAI, Grok/xAI oder Gemini). Ohne Key bleibt Ollama.

Status: `GET /api/nils/llm` (Agency-Auth)

## Was der Bot kann

- Normales Gespräch (Wetter, Ideen, Business), Text und Sprachnachricht  
- Aufträge / Kundenbefehle (Status SHY001, …), Riskantes mit „ja“  
- Funnel-Begleiter-Nachrichten (parallel zu E-Mail)

## Was er nicht ist

- Kein Kunden-Support-Kanal  
- Kein Ersatz für WhatsApp Business an Endkunden  
- Kein Cursor-Ersatz (Repo-Code)

## Secrets

| Key | Pflicht |
|-----|---------|
| `TELEGRAM_BOT_TOKEN` | ja |
| `TELEGRAM_OWNER_CHAT_ID` | ja (nach erstem /start) |
| `TELEGRAM_WEBHOOK_SECRET` | optional |
| `XAI_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` | optional (Cloud-Qualität) |

Status: `GET /api/nils/telegram-ops` (Agency-Auth)
