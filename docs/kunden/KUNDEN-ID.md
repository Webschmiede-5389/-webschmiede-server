# Kunden-ID (Projektnummer)

Jeder **Kunde** bekommt eine feste ID. **Leads** (z. B. Anfragen ohne Vertrag) haben **keine** ID und keinen Eintrag in `kunden/`.

## Format

```
SHY001
││└── Laufnummer (001, 002, …)
│└─── Branchen-Prefix (3 Buchstaben)
└──── Immer Großbuchstaben
```

## Branchen-Prefixe

| Prefix | Branche | Beispiel |
|--------|---------|----------|
| **SHY** | Gastro, Restaurant, Imbiss | SHY001 Snack House Yassine |
| **HWK** | Handwerk, Maler, Dach, Elektro | HWK001 |
| **BTY** | Beauty, Friseur, Kosmetik | BTY001 |
| **FIT** | Fitness | FIT001 |
| **MED** | Praxis, Arzt | MED001 |
| **RCH** | Kanzlei, Anwalt, Beratung | RCH001 |
| **IMB** | Immobilien | IMB001 |
| **KND** | Sonstiges (Fallback) | KND001 |

Neue ID vorschlagen:

```bash
python jarvis.py next-id restaurant   # → SHY002
python jarvis.py next-id handwerk     # → HWK001
```

## Wo die ID überall vorkommt

| Ort | Beispiel |
|-----|----------|
| Master-Datei | `kunden/SHY001_snackhouse.json` |
| Onboarding | `…/onboarding?k=SHY001` |
| Agency-Rechnung | `WS-2026-SHY001` |
| n8n Webhook | `/webhook/new-order-shy001` |
| Stripe Metadata | `kunde_id: SHY001` |
| Handout / Docs | `docs/kunden/SHY001-…` |

## Felder in `kunden/*.json` (pro Kunde)

```json
{
  "id": "SHY001",
  "n8n": {
    "order_webhook": "http://127.0.0.1:5678/webhook/new-order-shy001",
    "workflows": ["SHY001 - Neue Bestellung Alert", "SHY001 - Monats-Buchhaltung"],
    "provisioned_at": "2026-07-15T14:00:00Z"
  },
  "buchhaltung": { "bookkeeper_email": "" }
}
```

Automatisch bei `jarvis.py neu`. Manuell: `python jarvis.py n8n SHY001`

`buchhaltung.bookkeeper_email` = Mail der **Steuerberaterin/Buchhaltung des Kunden**, nicht global.

## Lead vs. Kunde

| | Lead | Kunde |
|---|------|-------|
| Beispiel | IVK / Anfrage ohne Vertrag | SHY001 Yassine |
| `kunden/*.json` | nein | ja |
| ID | nein | ja |
| Portal / CRM / n8n | nein | ja (pro ID getrennt) |

Lead wird Kunde: `python jarvis.py neu` oder Agency-Dashboard → neue ID vergeben.

## Status-Lebenszyklus

```
lead → angebot → test → live → pausiert
```

- **test:** Testphase (wie SHY001 jetzt)
- **live:** Kunde zahlt, produktiv
