# Gastro-Standard: Tischaufsteller + Kunden-CI

Für jeden Gastronomie-Kunden (Branche `restaurant` / `gastro` / …) gehören Tischaufsteller und Brand-Config zum Onboarding.

## Richtlinie (Gast)

1. **Tisch-QR** → Bestellen (erste Online-Bestellung z. B. 5 %)
2. **Theke** → wer nicht am Handy bestellt, bestellt normal
3. **Theke-QR** → Google-Bewertung (nicht als Haupt-QR auf dem Tisch)

## Onboarding

- Link: **Tischaufsteller mit QR** (`/ci/tischaufsteller.html?k=KUNDENID`)
- Aufgabe in der Checkliste: Aufsteller drucken
- Texte, Farben, Logo kommen aus `kunden/*.json` → Block `brand`

## Kunden-JSON `brand`

```json
"brand": {
  "logo": "/brand/{slug}-logo.png",
  "logo_shape": "diamond",
  "colors": {
    "gold": "#C9A84C",
    "gold_soft": "#F0D878",
    "dark": "#0e0b08",
    "ink": "#f5f0e8",
    "muted": "#a39888",
    "border": "#3a3228"
  },
  "font_display": "Playfair Display",
  "font_body": "Inter",
  "table": { "tag": "...", "headline": "...", "sub": "...", "promo": "...", "hint": "..." },
  "google": { "tag": "...", "headline": "...", "sub": "...", "promo": "...", "hint": "..." }
}
```

| **Papiermaß** | DIN A5 Hochformat, **148 × 210 mm** |
| **Tisch-Halter** | Acryl A5 Hochformat, **beidseitig** (T-Aufsteller / Menükartenhalter) |
| **Theke** | A5 einseitig reicht (Google-Seite) |
| **Shop-Suche** | „Tischaufsteller A5 Acryl beidseitig“ |

Maße stehen auch oben auf der Druckseite (sichtbar im Browser, nicht im PDF).

## Neuer Gastro-Kunde

1. `create_kunde` legt `brand` mit Gastro-Default an
2. Kundenlogo nach `app/static/brand/{slug}-logo.png`
3. Farben/Texte in `brand` anpassen
4. Onboarding öffnen → Tischaufsteller PDF
5. 5 %-Aktion im Admin anlegen (Aufsteller allein bucht keinen Rabatt)

## Code

| Datei | Rolle |
|-------|--------|
| `app/backend/client_brand.py` | Defaults + Merge |
| `app/backend/onboarding.py` | Link + Task + `brand` im API |
| `app/static/ci/tischaufsteller.html` | Druckvorlage A5 |
| `app/static/brand/` | Kundenlogos |

Referenz live: SHY001 Snack House Yassine.
