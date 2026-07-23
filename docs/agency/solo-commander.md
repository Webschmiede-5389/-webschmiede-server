# Solo-Commander (natives KI-Setup)

Stand: 2026-07-19

## Haltung

Du bist nicht „alleine ohne Hilfe“, sondern Commander ueber Router, Stefan, Scout, Texter, Anwalt, Nils.  
Ausfuehrung skaliert. **Abschluss und finale QA bleiben menschlich.**

## Was der Guru-Pitch falsch hat

| Claim | Wahrheit |
|-------|----------|
| Helsinki | **Nuernberg** |
| 95 % Marge / 30–50k easy | Orientierung hoechstens, **keine Garantie** |
| Alles in 3 Min fuer 35 Cent | Pack-API ja; Closing/QA/Onboarding = Stunden |
| Bot schliesst 5–10k | **Nein** – Zoom/Telefon durch Christian |
| Scout schon „an den Start“ | WF3/4 **waren schon live** – hier verdrahtet |

## Live

```bash
# Tageslage + Scout-Entwuerfe
python scripts/commander_cli.py --briefing

# Kapazitaet ehrlich (z. B. 6x5k = 30k Wunsch)
python scripts/commander_cli.py --capacity --ticket 5000 --target 30000 --hours-week 10

# Neues Projekt: Stefan + Anwalt + Texter/Design-Briefings
python scripts/commander_cli.py --fulfillment --firma "Mueller GmbH" --budget 5000 \
  "Wholesale Portal + Keepa-Listen"
```

API:
- `GET /api/agency/commander/briefing`
- `POST /api/agency/commander/capacity`
- `POST /api/agency/commander/fulfillment`

Scout/Outreach weiter: `docs/agency/scout-outreach.md`

n8n (inaktiv): `infra/n8n/agency-system/00-commander-briefing.json`

## Persoenliche Gates (nicht automatisierbar)

1. Trust-Abschluss  
2. Finale Dashboard-Freigabe  
3. Outreach- und DocuSeal-Freigabe  
4. Scope/Preis muendlich
