# Topic: Nils Dispatcher (Smart LLM Router)

Stand: 2026-07-20

## Beschluss

- Kein neues Node/TS-Projekt. Dispatcher in bestehendem Python-Backend.
- Modul: `app/backend/nils_dispatcher.py`
- `llm.chat()` nutzt Dispatcher standardmäßig (`NILS_DISPATCHER=1`)
- Route A/B/C, PII-Strip vor Cloud
- Primary Gateway: Requesty (`PRIMARY_LLM_GATEWAY` + `PRIMARY_API_KEY`)
- Fallback: OpenAI direkt (`FALLBACK_OPENAI_*`)
- Bezahlte Keys nur nach Christians OK
- Doku: `docs/agency/nils-dispatcher.md`
- Smoke: `python scripts/nils_dispatcher_smoke.py`

## Offen

- Echte `PRIMARY_API_KEY` / `FALLBACK_OPENAI_KEY` nur in Secrets (nie Chat)
- Route-C Vision (Bild-Multipart) noch dünn
- Requesty Modell-IDs ggf. anpassen (`NILS_ROUTE_*_MODELS`)
