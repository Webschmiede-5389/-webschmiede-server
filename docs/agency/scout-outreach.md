# Scout & Outreach (WF3/4)

Stand: 2026-07-19

## Haltung

Markt-Scout sucht und priorisiert. Outreach schreibt Entwuerfe.  
**Kein vollautomatischer Versand.** Kein Speedscaling-Spam.

## Live

```bash
python scripts/scout_campaign_cli.py --vertical gastro --limit 5 --ticket 5000
python scripts/stefan_plan_cli.py --growth --niche "Wholesale" --ticket 5000 "Portal + Keepa"
```

API:
- `POST /api/agency/scout/campaign`
- `POST /api/agency/scout/outreach-draft`
- `GET /api/agency/scout/queue`
- Freigabe: `POST /api/agency/akquise/approvals`
- Stefan Growth: `POST /api/agency/stefan/growth`

n8n (inaktiv): `03-scout.json`, `04-outreach.json`

## Frische Leads

Reports unter `docs/akquise/reports/`. Neu ziehen:

```bash
python -m akquise gastro
```

(Places-Key / Kosten beachten – nur mit OK.)

## Stefan Growth

Landing-Struktur, 3er E-Mail-Sequenz, Verkaufs-Schnitt.  
Alles Entwurf. Texter schreibt Feinschliff. Christian gibt frei.
