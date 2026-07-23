# Telegram Agency-Agent (Nils/Stefan)

Stand: 2026-07-19

## Ziel

Telegram ≈ Ops/Strategie-Kanal wie Cursor-Mitarbeiter, **nicht** Repo-Edit.

## Nutzung

- Normal schreiben → Nils + Tools + LLM
- `stefan: …` / `frag stefan …` → Stefan (Strategie)
- `nils: …` → Nils (Ops)
- Shortcuts: Alle Kunden, Status SHY001, Deals, Dual, Guardian
- Mails/Angebote: Bestätigung mit „ja“

## Technik

- `telegram_ops.py` → `telegram_agent.py` → Tools + `agency_brain` + `llm_client` (Ollama)
- Modell: möglichst `qwen2.5:14b` auf auto-01 (sonst 7b)
- n8n: `infra/n8n/workflow-telegram-ops.json` (Brain-Bridge)

## Meeting-Scan (beim Kunden)

Beispiel an den Bot:

```
https://firma-beispiel.de
max@firma-beispiel.de
Scanne die Firma und mach ein Angebot
```

Dann: Website-Research + Pain-Entwurf + Deal im Dashboard.  
Einladung an den Kunden erst nach deinem „ja“.

## Grenzen (ehrlich)

- Kein Code ändern im Repo
- Kein Auto-Spam an Kunden
- Research = Website-Signale, kein Fake-Trustpilot
- LLM halluziniert ohne Tool-Fakten – Tools zuerst
