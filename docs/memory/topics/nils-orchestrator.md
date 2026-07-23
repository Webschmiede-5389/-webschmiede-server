# Nils Orchestrator

Stand: 2026-07-20

## Live

Modul `nils_orchestrator.py`, verdrahtet in `telegram_agent.handle`.

Ablauf bei Arbeit (nicht Smalltalk):

1. Plan: Lead, Team (Router-Mitarbeiter), LLM-Route A/B/C, Tools, Cursor?, n8n-Katalog
2. Tools ausführen (Cursor/Mail mit Freigabe)
3. Agency-Brain dispatch
4. Texter-LLM wenn nötig
5. n8n Agency-Brain Webhook (fail-open)
6. Antwort mit Plan-Zeile oben

Telegram-Test: `Status SHY001 und was wir als Nächstes bauen sollten`

## Grenzen (ehrlich)

- Manche Mitarbeiter bleiben teilweise Stub/Handoff
- n8n-Trigger braucht erreichbaren Webhook (`N8N_WEBHOOK_BASE`)
- Cursor weiter mit Freigabe + Key
