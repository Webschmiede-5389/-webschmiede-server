# Topic: Ops-Guardian

Stand: 2026-07-19

## Beschluss

Christian will einen Alleskönner. Umsetzung: `ops_guardian` = maximaler sicherer Auto-Fix + zentrale Meldung. Kein Meta/Domain/Auth-Blind-Retry.

## Technik

- `app/backend/ops_guardian.py`
- Cron `*/15` web: `scripts/ops_guardian.sh`
- API `GET/POST /api/nils/guardian*`
- Setup `python scripts/setup_ops_guardian.py`

## Nächster Schritt

Live: Cron `*/15` auf web, Lauf yellow wegen WhatsApp-Tokens (Alert only). Surfaces grün.
