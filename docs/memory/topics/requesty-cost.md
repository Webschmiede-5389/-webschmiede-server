# Requesty / Nils Kosten

Stand: 2026-07-20

## Regeln

- Chat: günstige Modelle zuerst (Route A)
- Bilder: nie auto (`NILS_IMAGE_AUTO=0`)
- Bild-Job: Quote → Freigabe (`NILS_PAID_MEDIA_CONFIRM=1`)
- Soft: $8/Tag, $20/Monat, 5 Bilder/Tag
- Video: unsupported, kein Kauf
- Status: Telegram „budget“ / „kosten“

## Offen (Christian)

In Requesty Console hartes Monats-Limit $20 am API-Key setzen (API kann manage:none nicht).

## Code

`requesty_client.estimate_media_job`, `nils_ops.try_creative_generation(confirmed=…)`, Telegram pending `paid_image`
