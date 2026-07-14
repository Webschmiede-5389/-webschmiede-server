# Webschmiede – Strategie & Produktvision

> Gespeichert: Juli 2026 · Digitale Handwerkskunst (Digital Craftsmanship)

## Kernidee

**Eine Technologie-Plattform (Webschmiede), viele Branchen-Fassaden.**

- Gastro und Dachdecker/Händler passen **nicht** auf dieselbe Marketing-Seite.
- Alle Branchen teilen sich **dieselbe Engine** (Jarvis, Deploy, CRM, Bot, Automatisierung).
- Nach außen: **eigene Branchen-Homepage + Instagram** pro Nische.
- Nach innen: **ein Hub** (webschmiede.de) wie ein Holding-Modell (Vorbild: FlyRuwe — mehrere Marken/Unternehmen, eine übergeordnete Homepage).

```
webschmiede.de          ← Hub: „Digitale Handwerkskunst“
├── /gastro             ← eigene Probleme, Wizard, Demo, Instagram
├── /dachdecker
├── /trockenbau
└── …

Shared Backend:
  jarvis · kunden/*.json · deploy · bot · CRM · Akquise-Krieger
```

## Positionierung

| Begriff | Bedeutung |
|---------|-----------|
| **Digitale Handwerkskunst** | Oberbegriff — Qualität, Maßarbeit, aber digital |
| **Branchen-Nische** | Fokus pro Vertical (erst Gastro, dann erweitern) |
| **Nicht** | Eine Agentur-Seite mit „wir machen alles für alle“ |

**Fokus-Regel:** Pro Phase **eine Nische vertiefen** (Gastro mit Snack House als Referenz), dann nächste Branche mit **eigener Landing + eigenem Content**, nicht vermischt.

---

## Produkt-Schichten

### 1. Akquise (Akquise-Krieger)
- Nachts: lokale Betriebe scannen (Branche konfigurierbar)
- Bewertung: Website, SEO, Speed, Google-Auftritt, geschätztes Potenzial
- Output: Report + E-Mail-Entwurf (+ optional Demo-Preview)
- **Freigabe durch Inhaber** — kein Blind-Spam (UWG/DSGVO)

### 2. Verkaufs-Portal (Wizard)
- Interessent durch Umfrage führen
- **Forecast:** Was fehlt, was bringt es, was kostet es, was muss der Kunde selbst liefern (SMS-Key, Fotos)
- Paketwahl → Stripe → Auto-Onboarding startet

### 3. Auto-Onboarding
- `jarvis neu` → Kunden-JSON → Template klonen → Deploy → Preview-URL
- Checkliste im Kunden-Portal
- WhatsApp-Bot freischalten (Preise, Texte, Bilder)

### 4. Betrieb (wie SHY001)
- Bestellportal, Admin, CRM, SMS, Follow-ups, Bot-Log
- Kunde ändert Inhalte per WhatsApp (mit Rechte-Grenzen)

### 5. Marketing-Automatisierung (Webschmiede selbst)
- **Pro Branche:** eigener Instagram-Account
- Auto-Posts: Tipps, Before/After, Kundenprobleme, Case Studies
- Quellen: Branchen-Landing + generierte Inhalte — **Freigabe-Queue** am Anfang

---

## Branchen-Template-Modell

Jede Branche bekommt:

| Asset | Gastro | Dachdecker (später) |
|-------|--------|---------------------|
| Landing-Page | webschmiede.de/gastro | webschmiede.de/dach |
| Pain Points | Kein Online-Bestellen, Bewertungen | Keine Anfragen, schlechtes Mobil |
| Wizard-Fragen | Lieferung, Speisekarte, Stripe | Angebotsformular, Galerie, SEO lokal |
| Kunden-Template | order.html + admin | anfrage.html + admin |
| Instagram | @webschmiede.gastro | @webschmiede.dach |
| Akquise-Scanner | Google „Restaurant“ + Radius | Google „Dachdecker“ + Radius |

**Gemeinsam:** Auth, CRM-Pattern, Deploy, Bot-Engine, Datenschutz-Framework.

---

## Referenz & Reihenfolge

1. **SHY001 Snack House (Hassan Yassine)** — Referenz Gastro, alles live
2. **Hub-Seite webschmiede.de** — Holding, Links zu Branchen
3. **Gastro-Wizard + Forecast** — erster automatisierter Vertrieb
4. **Akquise-Krieger Gastro** — Umkreis Mechernich/Euskirchen
5. **Instagram Gastro** — Post-Pipeline mit Freigabe
6. **Zweite Branche** — erst wenn Gastro wiederkehrend Umsatz bringt

---

## Was der Kunde erlebt

1. Findet `webschmiede.de/gastro` (oder Akquise-Mail)
2. Macht 5–10 Min Wizard
3. Sieht Forecast + Demo-Preview
4. Bucht Paket
5. Bekommt Portal: Fortschritt, To-dos, WhatsApp-Bot
6. **Webschmiede erledigt den Rest** — Kunde nur Keys, Fotos, Freigaben

---

## Technische Anker (Repo)

| Komponente | Status |
|------------|--------|
| `jarvis.py` + `kunden/*.json` | ✅ |
| Snack House Stack | ✅ |
| WhatsApp-Bot + Test-Webhook | ✅ |
| Follow-up Automation | ✅ (SMS pending) |
| Bot-Log Admin | ✅ |
| Agency Dashboard | 🔲 |
| Verkaufs-Wizard | 🔲 |
| Akquise-Krieger | 🔲 |
| Multi-Branche Templates | 🔲 |
| Instagram Auto-Posts | 🔲 |
| GitHub + Cloud Agents | 🔲 empfohlen |

---

## Grundsätze

- **Eine Nische vertiefen, dann nächste** — nicht parallel zehn Branchen
- **Hub + Spokes** — eine Marke oben, Branchen getrennt unten
- **Automatisierung mit Freigabe** — besonders E-Mail, Instagram, Go-Live
- **DSGVO & UWG** — Dokumentation, Opt-in, keine Spam-Pipeline
- **Fakten + Quellen** — Akquise-Reports mit Belegen (Ladezeit, fehlendes SSL, etc.)

---

## Trend Scout & Wissens-Datenbank (Research Agents)

> Idee gespeichert: Juli 2026 · „Immer up to date bleiben — global scannen, lokal bewerten“

### Ziel

Autonome **Research-Agents** erweitern laufend eine **Webschmiede-Wissensdatenbank** und liefern **regelmäßige Reports**:

- Virale CTAs, Funnel-Designs, Landing-Patterns (USA → DE-Adaption prüfen)
- Marketing-Automationen, die in DE noch unbekannt oder untergenutzt sind
- **Neue Nischen** jenseits klassischem Handwerk/Gastro (z. B. Creator Economy, Booking-only Services, Micro-SaaS für Lokale)
- Bewertung: **Macht das für den deutschen Markt Sinn?** (Recht, Kultur, Zahlungsverhalten, DSGVO)
- Empfehlung: **In welche Nische, in welcher Form, welche Automation als Nächstes?**

### Architektur (Hub-and-Spoke für Intelligence)

```
┌─────────────────────────────────────────────────────────┐
│  TREND SCOUT (Cron / wöchentlich + bei Bedarf)          │
│  Quellen: US/UK Marketing, Product Hunt, Reddit,        │
│  Twitter/X, YouTube, DE Branchenforen, Wettbewerber     │
└──────────────────────────┬──────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────┐
│  WISSENS-DB (SQLite / später Vector-Search)             │
│  trends · niches · ctas · automations · reports         │
└──────────────────────────┬──────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────┐
│  BEWERTUNGS-AGENT (DE-Fit-Score)                        │
│  Recht · Zielgruppe · Umsetzbarkeit mit unserem Stack   │
└──────────────────────────┬──────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────┐
│  REPORT an Inhaber (E-Mail / Admin / Cursor)            │
│  „Diese Woche: 3 Chancen · 1 Nische neu · 2 ignorieren“   │
└─────────────────────────────────────────────────────────┘
```

### Was jeder Report enthält

| Feld | Inhalt |
|------|--------|
| **Trend** | Was ist viral / wächst (Quelle + Link) |
| **Ursprung** | US / UK / DE / anderer Markt |
| **DE-Adaption** | Was funktioniert 1:1, was muss angepasst werden |
| **Automation** | Konkret: Bot, Funnel, CRM, Content-Pipeline |
| **Nische** | Gastro / Handwerk / Creator / … oder **neu vorgeschlagen** |
| **Score** | Potenzial 1–10, Aufwand, Risiko (Recht/DSGVO) |
| **Empfehlung** | **Go / Watch / Ignore** + nächster Schritt |
| **Webschmiede-Fit** | Passt zu Hub, braucht neues Branchen-Template? |

### Spezialregel: US-Marketing mit deutschem Anstrich

Viele US-Tools/Agenturen klingen auf Deutsch marketing-tauglich, passen aber nicht:

- Aggressive CTAs („Book a call NOW!!!“) → DE oft zu pushy
- SMS/Email-Frequenz → UWG/DSGVO enger
- Pricing-Psychologie → Netto, Impressum, Widerruf
- **Scout markiert:** „US-Idee X → DE-Variante Y“

### Nischen-Entdeckung (nicht nur Handwerk)

Scout sucht bewusst **unterversorgte Verticals**:

- Hohe Digitalisierungslücke + wiederkehrender Umsatz
- Automatisierbar mit unserem Stack (Portal, Bot, CRM, Content)
- Beispiel-Kategorien (nur als Denkrichtung): Creator/Coaching, lokale Services, Termin-heavy Branchen, B2B-Micro-Nischen

**Filter:** Nur Nischen, die zu „Digitale Handwerkskunst“ passen (Qualität, Betrieb, nicht reine Spam-Pipelines). Explizit **keine** illegalen/grauen Märkte.

### Laufzeit

| Komponente | Wo |
|------------|-----|
| Cron (z. B. Mo 07:00) | Server |
| Scraping/APIs | Server (rate-limited, robots.txt) |
| LLM-Synthese | API-Key auf Server oder Cursor Cloud |
| Report | E-Mail + Tab **Intelligence** im Agency-Dashboard |
| Freigabe | Neue Nische → du entscheidest **Go** |

### Phasen

1. **Manueller Weekly Report** (Agent per Cursor Cloud, Template)
2. **Wissens-DB + Quellen-Feeds** (RSS, APIs, gespeicherte Snippets)
3. **DE-Fit-Scoring automatisiert**
4. **Integration Akquise-Krieger** („Trend X → neue Branche Y scannen“)
5. **Instagram/Content-Agent** zieht aus derselben DB

### Grundsätze

- **Global lesen, lokal entscheiden** — nicht blind US kopieren
- **Quellen pflichtig** — jede Empfehlung mit Beleg
- **Du behältst Strategie** — Agents schlagen vor, du gibst Nische frei
- **Fokus trotz Scout** — max. 1–2 neue Nischen gleichzeitig testen

---

## Social Media Pipeline — German Golf Guide (Nischen-Modul)

> Gespeichert: Juli 2026 · Content-Automation via n8n + Meta API · **Eigene Kanäle ja — fremde Profile nein**

### Ziel

Automatisierter **Content-Funnel** für eine Golf-Nische (z. B. „German Golf Guide“):

- Trends / virale Hooks recherchieren (global → DE Golf adaptieren)
- Copywriting (Captions, Hooks, Hashtags)
- Grafik aus Brand-Templates (Canva / Bannerbear / Placid)
- Instagram + Facebook **planen und veröffentlichen**
- **Eigene** Kommentare auf **eigenen** Posts beantworten (Vorschlag + Freigabe)
- Content-Historie / Kalender

### Bewusst **nicht** im Scope (Meta ToS / Sperrgefahr)

| Verboten / nicht bauen | Grund |
|------------------------|--------|
| Automatisch fremde Golf-Profile kommentieren | Instagram/Meta ToS |
| Auto-Liken / Follow / Scroll-Engagement | Bot-Erkennung, Account-Sperre |
| 100 % Publish ohne Freigabe (Phase 1) | Marken- & Rechtsrisiko |

**Alternative (halbmannuell):** n8n liefert täglich **5 Engagement-Vorschläge** (Link + Kommentartext) → Mensch postet selbst.

### Agent-Rollen

| Agent | Aufgabe |
|-------|---------|
| **Research-Agent** | Trends Golf/DE, Wettbewerber-Posts **lesen** (kein Posting fremd) |
| **Creative-Agent** | Text + Bild-Entwurf aus Templates |
| **Publisher-Agent** | Meta Graph API — planen & posten nach Freigabe |
| **Community-Agent** | Nur **eigene** Kommentare — Antwort vorschlagen oder Regel-basiert |
| **Controller** | Freigabe-Queue (Telegram / n8n / Agency-Dashboard) |

### Technischer Stack

```
Trend Scout (Golf/DE)
       │
       ▼
    n8n Workflow
       ├── LLM (OpenAI/Claude) → Copy + Hooks
       ├── Canva/Bannerbear → Grafik aus Template
       ├── Freigabe (Telegram / WhatsApp an Inhaber)
       └── Meta Graph API → Instagram Business + Facebook Page
                │
                └── Webhook → Kommentare auf EIGENEN Posts → Antwort-Vorschlag
```

### Einmalige Voraussetzungen

- Instagram **Business** + Facebook **Page** verknüpft
- Meta Developer App + OAuth (Long-lived Token)
- API-Keys: LLM, Canva o. ä.
- Brand-Template (Farben, Logo, Schriften — DSGVO: Bunny Fonts)
- n8n auf Server (`/n8n/`) — bereits installiert

### Typischer Wochen-Flow

| Schritt | Wann | Was |
|---------|------|-----|
| Research | Mo 06:00 | 3 Post-Ideen + Hooks aus Trends |
| Creative | Mo 06:30 | Caption + Grafik-Entwurf |
| Freigabe | Mo 08:00 | Push an Inhaber — Ja/Nein/Edit |
| Publish | Di/Do/Sa 18:00 | IG + FB geplant |
| Community | laufend | Eigene Kommentare → Vorschlag → Freigabe |

### Paket-Stufen (verkaufbar)

| Stufe | Inhalt |
|-------|--------|
| **Social Starter** | 3 Posts/Woche Entwurf + Freigabe + manuelles Posten |
| **Social Pro** | Auto-Planung IG+FB, Templates, Kommentar-Vorschläge |
| **Social Premium** | + Trend Scout Golf/DE, Engagement-Vorschläge (manuell posten) |

### Phasen (Implementierung)

1. Brand-Template + Meta-Anbindung + n8n Posting mit **Pflicht-Freigabe**
2. Trend Scout Feed Golf/DE in Content-Queue
3. Kommentar-Agent (nur eigene Posts)
4. Engagement-Digest (Vorschläge für fremde Profile — **ohne Auto-Post**)
5. Optional: zweite Nische (Gastro `@webschmiede.gastro`) — gleiche Engine, anderes Template

### Verbindung zum Hub

- **webschmiede.de/golf** (später) — eigene Landing, eigene Pain Points
- **@germangolfguide** (Beispiel) — eigener Instagram, getrennt von Gastro
- **Gleiche Engine:** n8n, Trend Scout, LLM, Freigabe-Queue

### Grundsatz

> **Eigene Kanäle automatisieren — fremde Kanäle nicht beackern.**

---

*Siehe auch: Akquise-Krieger, Verkaufs-Wizard, Branchen-Templates, Trend Scout oben in diesem Dokument.*

