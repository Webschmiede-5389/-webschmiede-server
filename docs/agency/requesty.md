# Requesty (Nils Vollzugriff)

Stand: 2026-07-20

Ein Gateway-Key (`PRIMARY_API_KEY` / `requesty.secrets.local`) → Chat, Vision, Bild-Generierung über Requesty.

## Kostenfalle-Schutz (Pflicht)

| Regel | Default |
|-------|---------|
| Chat | immer **billigste brauchbare** Modelle zuerst (Route A) |
| Bilder | **nie automatisch** (`NILS_IMAGE_AUTO=0`) |
| Bild-Job | erst Kostenvoranschlag, dann „ja“ (`NILS_PAID_MEDIA_CONFIRM=1`) |
| Tages-Budget | `$8` (`NILS_REQUESTY_DAILY_BUDGET`) |
| Monats-Budget | `$20` (`NILS_REQUESTY_MONTHLY_BUDGET`) |
| Bilder/Tag | max `5` (`NILS_IMAGE_MAX_PER_DAY`) |
| Video | nicht verfügbar, kein Auto-Kauf |
| Status | Telegram: `budget` oder `kosten` |

Zusätzlich in der Requesty-Console hartes Monats-Limit am API-Key setzen (UI, nicht nur Soft-Guard).

## Was geht

| Fähigkeit | Wie |
|-----------|-----|
| ~560 Chat-Modelle | `GET /v1/models`, Dispatcher Route A/B/C |
| Bild / Logo | erst Quote → Freigabe → `POST /v1/images/generations` |
| Bild verstehen | Vision über Requesty |
| Katalog | `/api/nils/requesty/models`, Status in `/api/nils/llm` |

## Was nicht geht (ehrlich)

- **Video erzeugen** (Reels/Sora/Runway): Requesty liefert das bei uns nicht.
- „500 Modelle = immer billigster und bester gleichzeitig“: Router wählt **gute + günstige** Kette, nicht Magie.

## Env

```bash
PRIMARY_LLM_GATEWAY=https://router.eu.requesty.ai/v1
PRIMARY_API_KEY=…
NILS_REQUESTY_DAILY_BUDGET=8
NILS_REQUESTY_MONTHLY_BUDGET=20
NILS_IMAGE_MAX_PER_DAY=5
NILS_IMAGE_AUTO=0
NILS_PAID_MEDIA_CONFIRM=1
```

## Code

- `requesty_client.estimate_media_job` / `format_cost_quote` / `spend_status_text`
- `nils_ops.try_creative_generation(..., confirmed=False|True)`
- Telegram: pending `paid_image` → ja/abbrechen
