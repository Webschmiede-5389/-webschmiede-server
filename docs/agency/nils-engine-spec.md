# Nils Engine – optimierte Architektur (aus Prompt)

Stand: 2026-07-20

## Urteil zum Prompt

Der Prompt ist als **Greenfield Node/Fastify/Docker** gedacht. Bei uns läuft schon:

- Flask + Gunicorn (`snack-api`) auf Hetzner
- Telegram-Webhook unter `/api/telegram/webhook`
- `nils_dispatcher` + `requesty_client` + Dual-Gateway

Deshalb: **keinen Parallel-Stack**. Prompt-Ideen in den bestehenden Python-Stack einarbeiten.

## Was wir übernehmen / schärfen

| Prompt-Idee | Entscheidung |
|-------------|--------------|
| Requesty EU (Frankfurt) | Ja → `https://router.eu.requesty.ai/v1` |
| EU-Inference-Modelle | Ja, beste aus Katalog (siehe Routen) |
| OpenAI Direct Fallback | Ja, nur wenn `FALLBACK_OPENAI_KEY` gesetzt |
| Smart Router A/B/C | Ja, EU-Modellketten |
| Telegram Streaming + Debounce | Ja (`editMessageText`, ~400ms) |
| Bypass bei 5xx/Timeout | Ja, Kette + Connect-Timeout 5s |
| „200ms Gateway-Failover“ | **Nein** (unseriös) |
| „First Token &lt; 200ms“ | **Nein als Garantie** (Smoke: ~380ms Vollantwort Llama EU) |
| Fastify/TypeScript/Docker neu | **Nein** |

## DSGVO-Schichten (ehrlich)

1. **Lokal:** Ollama auf auto-01 (Daten bleiben auf dem Server) – Route A zuerst
2. **Requesty EU:** Processing/Logs in Frankfurt
3. **EU-Modelle:** Inference in EU (`@eu-central-1`, `@swedencentral`, Nebius/Mistral EU, …)
4. **PII-Strip** vor Cloud (`NILS_STRIP_PII=1`)
5. **OpenAI Direct:** nur Notfall, AVV nötig, nicht Default

EU-Endpoint allein reicht nicht. Ohne EU-Modell-ID kann Inference trotzdem außerhalb der EU landen (Requesty-Doku).

## Beste Modelle (Smoke 2026-07-20, EU-Gateway OK)

| Route | Zweck | Kette (Primary) |
|-------|--------|-----------------|
| **A** | Speed/Chat | Ollama → `nebius/meta-llama/Llama-3.3-70B-Instruct` → `tensorx/deepseek-v4-flash` → `mistral/mistral-small-latest` → `azure/gpt-4o-mini@swedencentral` |
| **B** | Logic/Code | `bedrock/claude-sonnet-4@eu-central-1` → `vertex/claude-sonnet-5@eu` → `tensorx/deepseek-v4-pro` → `mistral/mistral-medium-3-5` |
| **C** | Vision/JSON | `azure/gpt-4o-mini@swedencentral` → `bedrock/claude-sonnet-4@eu-central-1` → `mistral/mistral-small-latest` |
| Bild | Logos/IG | `azure/openai/gpt-image-1` |

Verworfen aus Prompt: generisches „DeepSeek V3 / Claude 3.5“ ohne Region – zugunsten gemessener EU-IDs.

## Failover (real)

- Connect-Timeout: 5s (`LLM_CONNECT_TIMEOUT`)
- Bei 5xx / Timeout / empty → nächstes Modell in der Route
- OpenAI Direct nur wenn Key gesetzt
- Kein „unsichtbar &lt;200ms“ – ehrlich in Logs (`attempts`, `dispatch_ms`)

## Telegram Streaming

- `NILS_TG_STREAM=1`
- Placeholder `…` + `sendChatAction typing`
- SSE von Requesty → `editMessageText` alle ~400ms oder ~5 Wörter
- Rate-Limit-schonend (Telegram 429 vermeiden)

## Deploy

Weiterhin `python deploy.py` (kein Docker-Zwang). Env: `requesty.secrets.local` → Server `/root/app/requesty.secrets.local`.

## Dateien

- `nils_dispatcher.py` – Routen + `dispatch_stream`
- `llm_client.py` – EU-Default, Connect-Timeout, SSE
- `telegram_ops.py` – `send_streaming_llm`
- `requesty_client.py` – EU-Defaults + Bild/Vision
