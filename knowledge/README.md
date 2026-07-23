# Knowledge Packs (Webschmiede)

Branchen-Wissen für Bot, Inbox-Agent und später Voice.

**Nicht verwechseln:** Agentur-Gedächtnis für Cursor-Chats liegt unter [`docs/memory/`](../docs/memory/README.md) (CURRENT, Handoff, Beschlüsse).

## Struktur

```
knowledge/packs/{pack_id}.json
kunden/{KID}_{slug}.json  →  "knowledge": { "pack": "gastro", "overrides": {} }
```

## Pack wählen

| Branche | Pack |
|---------|------|
| restaurant, gastro | gastro |
| handwerk, dach, dental, friseur | handwerk (oder eigenes Pack später) |
| sonstiges | general |

## Overrides pro Kunde

In `kunden/*.json`:

```json
"knowledge": {
  "pack": "gastro",
  "locale": "de-DE",
  "overrides": {
    "faqs": [
      { "id": "oeffnungszeiten", "answer": "Mo–Sa 11–22 Uhr, So 12–21 Uhr." }
    ]
  },
  "voice": { "enabled": false, "provider": "", "voice_id": "" }
}
```

## API

- `GET /api/agency/knowledge/{KID}` (Agency-Login)
- Loader: `app/jarvis/knowledge.py`

## Deploy

Packs liegen unter `/root/app/knowledge/packs/` (siehe `deploy.py`).
