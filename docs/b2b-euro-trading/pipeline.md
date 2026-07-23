# Pipeline: Produkt → Wholesale-Lead

## Ablauf

```
EAN / Marke / Produktname
        │
        ▼
┌───────────────────┐
│ Preisvergleiche   │  Idealo, Geizhals, billiger
│ + Marktplatz-Offers│  Kaufland, MMS, Conrad, OTTO, Hood
└─────────┬─────────┘
          │ Seller-Name, Shop-URL, Preis, Versand
          ▼
┌───────────────────┐
│ Enrichment        │  Impressum, USt-ID, Domain, Adresse
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Multi-Channel     │  Badges, gleiche Firma auf Amazon/eBay/…
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Score             │  aktiv, ≥2 Kanäle, B2B-Impressum, Sortiment-Fit
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Freigabe          │  Anrufen / Mail / Skip (wie Akquise)
└─────────┬─────────┘
          │
          ▼
     Wholesale-Angebot
```

## Score (Vorschlag)

| Signal | Punkte |
|--------|--------|
| Gewerbliches Impressum (GmbH/UG/e.K.) | +3 |
| ≥2 Marktplätze nachweisbar | +3 |
| Eigen-Shop (Shopify/Shopware) | +2 |
| Frisches Angebot / Lager sichtbar | +2 |
| Region DE/EU + USt-ID | +2 |
| Nur Privat / Dropship-Spam-Muster | −5 |
| Nur Amazon ohne Firma | −2 |

Ab Score 6: Freigabe-Queue.

## Angebot (Ton)

Kurz, konkret, kein Agentur-Gelaber:

- Was du lieferst (SKU, MOQ, Preisstaffel)  
- Warum der Händler passt (führt schon Marke X / Kanal Y)  
- Ein Call-to-Action (Mail / Termin)

## Datenfelder (Lead)

```json
{
  "ean": "",
  "product_title": "",
  "seller_name": "",
  "shop_url": "",
  "impressum_url": "",
  "company": "",
  "vat_id": "",
  "email": "",
  "phone": "",
  "channels": ["kaufland", "amazon", "ebay"],
  "sources": ["idealo", "kaufland"],
  "score": 0,
  "status": "pending"
}
```

## Pilot-Scope (empfohlen)

- 1 Marke oder 5–20 EANs  
- Quellen: Idealo + Kaufland + MediaMarkt  
- 50 Leads manuell freigeben  
- Dann Automation nur für Enrichment + Score
