# Nils Dispatcher (Smart-LLM-Router)

Stand: 2026-07-20

Chef-Dispatcher für Telegram-Nils: wählt Route A/B/C, maskiert sensible Daten vor Cloud, fällt bei Ausfall auf das nächste Modell zurück.

## Architektur (kein Parallel-Stack)

```
Telegram / Agency-Chat
        ↓
  llm_client.chat(..., route=?)
        ↓
  nils_dispatcher.dispatch
        ├─ classify A/B/C (Regeln, kein Extra-Call)
        ├─ strip_pii (IBAN, Mail, Telefon, Secrets)
        └─ Modell-Kette mit Fallback
              ├─ Ollama (gratis, lokal)
              ├─ OpenRouter (Gateway, optional)
              └─ OpenAI / Grok / Gemini (optional)
```

Sprache bleibt über Voice-Gateway / Whisper wie bisher (`llm_client.transcribe_audio_file`).

## Routen

| Route | Wann | Default-Kette |
|-------|------|----------------|
| **A** | Chat, Format, Plan-JSON, kurz | Ollama → DeepSeek → Llama 3.3 → GPT-4o-mini |
| **B** | Code, Strategie, lange Analyse | Claude Sonnet → DeepSeek R1 → GPT-4o → Ollama |
| **C** | Bild/PDF/Beleg → strukturiert | GPT-4o → Claude → Ollama |

Modelle per Env überschreibbar: `NILS_ROUTE_A_MODELS`, `NILS_ROUTE_B_MODELS`, `NILS_ROUTE_C_MODELS`  
Format: `provider:model,provider:model,…`

## Env (Auszug)

```bash
NILS_DISPATCHER=1
NILS_STRIP_PII=1
LLM_PROVIDER=auto
OLLAMA_URL=http://AUTO_HOST:11434
OLLAMA_MODEL=qwen2.5:14b

# Primäres Gateway (Requesty / EU-Smart-Router)
PRIMARY_LLM_GATEWAY=https://router.requesty.ai/v1
PRIMARY_API_KEY=
PRIMARY_LLM_MODEL=gpt-4o-mini

# Fallback Direkt-OpenAI
FALLBACK_OPENAI_GATEWAY=https://api.openai.com/v1
FALLBACK_OPENAI_KEY=
```

Keys nur in `deploy.secrets.local` / Agency-Keys, nie in Git oder Chat.

Agency-UI: `/agency-keys` → Gruppe „KI (Nils / Jarvis)“.

## Reihenfolge

1. Ollama (gratis, lokal)
2. **Primary** (`PRIMARY_LLM_GATEWAY` + `PRIMARY_API_KEY`)
3. OpenAI Fallback (`FALLBACK_OPENAI_*` / `OPENAI_API_KEY`)
4. OpenRouter / Grok / Gemini (optional)

## Datenschutz (ehrlich)

- **ZDR** (Zero Data Retention) ≠ „DSGVO fertig“.
- OpenRouter-Calls setzen `provider.data_collection=deny` wo möglich.
- Vor Cloud: Data Stripping.
- Ollama lokal: Daten bleiben auf dem Server.
- AVV bei Hetzner/OpenAI/OpenRouter bleibt deine Aufgabe.

## Fallback

Kein Fake-„&lt;100ms“-Versprechen. Bei Fehler (Timeout, 5xx, empty) sofort nächstes Modell in der Kette. Am Ende klassischer `llm.chat(use_dispatcher=False)`.

## Lokal testen

```bash
cd app/backend
python ../../scripts/nils_dispatcher_smoke.py
```

Ohne Keys: nur Classify + Strip. Mit Ollama: kurzer Route-A-Call.

## Deploy

```bash
python deploy.py
```

Backend-Neustart lädt `nils_dispatcher.py` mit. OpenRouter-Key nur setzen, wenn du Cloud freigibst.

## Dateien

- `app/backend/nils_dispatcher.py`
- `app/backend/llm_client.py`
- `app/backend/telegram_agent.py` (Routen-Hints)
- `app/backend/.env.example`
- `app/backend/agency_secrets.py`
