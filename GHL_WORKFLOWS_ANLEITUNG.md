# GHL Automation Guide – Snack House Yassine

> **OBSOLET seit 2026-07 (Snack House GHL Cut).**  
> Bestellungen und Kundendaten laufen über `webschmiede-server` (eigenes Portal + SMS/n8n).  
> Diese Anleitung nur noch als historische Referenz — keine neuen Workflows in GHL einrichten.

**Wo einrichten (historisch):** GHL → Automation → Workflows → + New Workflow → Start from Scratch

---

## WICHTIG ZUERST: SMS-Nummer kaufen
**GHL → Settings → Phone Numbers → + Buy Number**
- Land: Deutschland (+49)
- Danach muss die Nummer verifiziert werden

---

## WORKFLOW 1 – Neue Bestellung (sofortige Benachrichtigung)

**Trigger:** `Contact Tag` → Tag hinzugefügt = `neukunde`

### Schritt 1: SMS an Hassan (intern)
**Typ:** Send SMS  
**An:** [Hassans Handynummer eintragen, z.B. +491751234567]  
**Text:**
```
NEUE BESTELLUNG!
Nr: {{contact.customField.bestellnummer}}
Von: {{contact.firstName}} {{contact.lastName}}
Tel: {{contact.phone}}
Art: {{contact.customField.bestellart}}
Zeit: {{contact.customField.wunschzeit}}
Zahlung: {{contact.customField.zahlungsart}}
────────────
{{contact.customField.bestellinhalt}}
────────────
GESAMT: {{contact.customField.bestellbetrag}} EUR
```

### Schritt 2: SMS an Kunden (Eingangsbestätigung)
**Typ:** Send SMS  
**An:** {{contact.phone}}  
**Text:**
```
Hallo {{contact.firstName}}!
Deine Bestellung bei Snack House Yassine ist eingegangen.
Bestellung: {{contact.customField.bestellnummer}}
Voraussichtlich: {{contact.customField.wunschzeit}}

Wir melden uns kurz. Fragen? Ruf uns an: 02443-3088966
```

---

## WORKFLOW 2 – In Zubereitung

**Trigger:** `Opportunity Stage Changed` → Stage = `In Zubereitung`

### Schritt 1: SMS an Kunden
**Typ:** Send SMS  
**An:** {{contact.phone}}  
**Text:**
```
Hey {{contact.firstName}}!
Deine Bestellung wird gerade frisch zubereitet.
Bestellnr: {{contact.customField.bestellnummer}}

Noch kurz Geduld – gleich ist es soweit!
– Snack House Yassine
```

---

## WORKFLOW 3 – Unterwegs / Abholbereit

**Trigger:** `Opportunity Stage Changed` → Stage = `Unterwegs / Abholbereit`

### Schritt 1: SMS Lieferung (mit Bedingung)
**Bedingung:** IF Tag enthält `lieferung`  
**Typ:** Send SMS  
**Text:**
```
Auf dem Weg!
Hey {{contact.firstName}}, deine Bestellung ist unterwegs!
Unser Fahrer ist in ca. 15–25 Minuten bei dir.

Guten Hunger wünscht Snack House Yassine!
```

### Schritt 2: SMS Abholung (mit Bedingung)
**Bedingung:** IF Tag enthält `abholung`  
**Typ:** Send SMS  
**Text:**
```
Abholbereit!
Hey {{contact.firstName}}, deine Bestellung wartet auf dich!

Snack House Yassine
Dr.-Felix-Gerhardus-Str. 7, 53894 Mechernich

Wir freuen uns auf deinen Besuch!
```

---

## WORKFLOW 4 – Bewertungsanfrage (24h nach Abschluss)

**Trigger:** `Opportunity Stage Changed` → Stage = `Abgeschlossen`

### Schritt 1: Warten
**Typ:** Wait → 1 Tag (24 Stunden)

### Schritt 2: SMS Bewertungsanfrage
**Typ:** Send SMS  
**Text:**
```
Hey {{contact.firstName}}!
Wie hat dir deine Bestellung bei Snack House Yassine geschmeckt?

Wir würden uns über eine kurze Google-Bewertung freuen:
[GOOGLE REVIEW LINK EINTRAGEN]

Danke und bis bald!
– Dein Snack House Team
```

### Schritt 3: Tag hinzufügen
**Typ:** Add Tag → `bewertung-angefragt`

> **Google Review Link:** Google Business Profile → Rezensionen → "Rezensionen erhalten" → Link kopieren

---

## WORKFLOW 5 – Stammkunden-Upgrade (nach 3. Bestellung)

**Trigger:** `Field Updated` → Custom Field `Anzahl Bestellungen` = 3

### Schritt 1: Tag wechseln
**Typ:** Remove Tag → `neukunde`  
**Typ:** Add Tag → `stammkunde`

### Schritt 2: SMS Stammkunde
**Typ:** Send SMS  
**Text:**
```
Hey {{contact.firstName}}!
Du bist jetzt offiziell Stammkunde bei Snack House Yassine!

Als kleines Dankeschön gibt es bei deinem nächsten Besuch eine Überraschung von Hassan persönlich.

Bis bald! – Snack House Yassine
```

---

## WORKFLOW 6 – Re-Engagement (14 Tage inaktiv)

**Trigger:** `Date/Time` → 14 Tage nach `Letzte Bestellung` (Custom Field)  
**Filter:** Tag enthält `neukunde` ODER `stammkunde`

### Schritt 1: SMS Re-Engagement
**Typ:** Send SMS  
**Text:**
```
Hey {{contact.firstName}}!
Wir vermissen dich bei Snack House Yassine!

Heute auf der Karte:
- Frischer Schawarma
- Steinofen-Pizza
- Döner & Burger

Jetzt online bestellen:
http://167.233.211.170/bestellen

Bis bald! – Dein Snack House Team
```

### Schritt 2: Tag hinzufügen
**Typ:** Add Tag → `re-engagement`

---

## OFFENE PUNKTE (nach diesem Guide)

| Aufgabe | Wer |
|---|---|
| Hassans Handynummer in Workflow 1 eintragen | Du |
| Google Review Link in Workflow 4 eintragen | Hassan |
| Domain statt IP-Adresse in WF-6 eintragen | Nach Domain-Setup |
| Stripe Payment Link ergänzen | Nach Stripe-Setup |
| GHL SMS-Nummer kaufen & verifizieren | Du |

---

## STAGE IDs (für eigene Skripte)
```
Pipeline:            car4PPqwg8kIIr20Hbdt
Stage Neue Best.:    5cb90e54-da95-41d8-b1d7-7e141364aabf
Stage In Zubereitung:a0aee420-abc3-4798-9a70-2359b6b98657
Stage Unterwegs:     49f4dcf1-3c93-4044-9457-3746ba82d546
Stage Abgeschlossen: 2e553b58-536e-4ac6-b4de-7c3e646463d2
Stage Storniert:     3abcaeed-9bdc-4154-bf85-6139a30065e2
```
