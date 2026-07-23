# Telegram Ops (Nils)

Stand: 2026-07-20

## Status

Live: Token + Chat-ID + Webhook + Requesty EU (fast path).  
Krisenfest v3: Dedup Memory+SQLite, Session-Isolation, 429-Retry, Soft-Errors.

## Schutzmechanismen

1. Webhook ACK sofort (`queued`), Arbeit im Thread-Pool (max 4)
2. Dedup: In-Memory `update_id`/`message_id` 60s + SQLite `telegram_updates`
3. Chat-Lock + Busy-Notice (kein stilles Drop)
4. History: `telegram_chat_turns` + Memory, nur user/assistant, pro chat_id
5. LLM-Messages via `telegram_session.build_llm_messages` (system nie aus History)
6. Telegram API `_tg_api` mit 429/5xx Backoff
7. Soft-Error: „Entschuldige Christian, da gab es eine kurze Verbindungsstörung…“
8. Voice: `record_voice` → Download → STT → Router (nach ACK)

## Dateien

- `app/backend/telegram_session.py` (neu)
- `app/backend/telegram_ops.py`
- `app/backend/telegram_agent.py`
- `app/backend/human_voice.py`
- `app/backend/main.py` Webhook

## Test (Christian)

1. Einmal „Hey“ → genau eine Antwort
2. Schnell zwei Nachrichten hintereinander → Busy-Hinweis oder geordnete Antworten
3. Sprachnachricht → Transkript-Verständnis, dann Antwort
