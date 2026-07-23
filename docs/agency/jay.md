# Jay / Jarvis Voice

Stand: 2026-07-17

## Live

https://digitalehandwerkskunst.de/jay

## Default

Stimme **Webschmiede Christian** (Retell Clone).  
Persönlichkeit: Kollege Jay. Stil: freundlich.

## Wählbar in der App

- Stimmen: Christian, Max, Carola, Eva, Lina, Nico
- Persönlichkeiten: Kollege, Sparring, Verkauf, Technik, Ruhig
- Akzent/Stil: Hochdeutsch, Rheinland, Kölsch, Bayrisch, …

## Technik

- Retell Web-Call (`/api/jay/session`)
- Agent Meta: `agency/jay_retell.json`
- Setup: `python scripts/setup_jay_retell.py`
- Modul: `app/backend/jay_voice.py`
- UI: `app/static/jay.html`

## Kosten & Schutz

- Agency-Login Pflicht
- Haken „Minuten kosten“ vor Start
- **Max. 3 Min.** pro Gespräch (Retell hard cut)
- **45 Sek.** Stille → Ende
- **30 Min./Tag** Budget (konservativ reserviert)
- Max. **6 Starts/Stunde**
- Secrets optional: `JAY_MAX_CALL_SECONDS`, `JAY_DAILY_MAX_SECONDS`, `JAY_SESSIONS_PER_HOUR`

Typisch reichen 2–3 Minuten. Länger: Limits in Secrets hochsetzen.
