# Webschmiede – Mitarbeiter & Stellenplan

> Stand: 17.07.2026 · Für Christian Kummetat · Ziel: Agentur die mehr kann als „Website + GHL-SMS“

---

## Kurz: Wie wir uns abheben

Die Konkurrenz verkauft oft:
- eine Website
- ein paar Formulare
- SMS/WhatsApp über GoHighLevel

Wir verkaufen **Betriebssystem für lokale Betriebe**:
- Bestell-/Anfrage-Portal + Inhaber-Dashboard
- eigenes CRM (kein GHL)
- Automatisierung (n8n, Follow-ups, Inbox)
- Akquise-Scanner pro Branche
- Voice (Demo selbst, Kunden später Retell)
- Seminare + Cal.com
- Nachts Watchdog, der Fehler findet bevor der Kunde meckert

Das ist **Handwerk digital**, nicht Agentur-Folie.

---

## Führung (KI-Team)

| Rolle | Name | Job |
|-------|------|-----|
| Inhaber | **Christian** | Verkauf, Freigaben, Gesicht |
| Betriebsleiter / Treiber | **Stefan (KI)** · **aktiv** | Tempo, Priorität, Vorausschau, führt alle Mitarbeiter |
| Ops / Plattform / Nachtwache | **Nils (KI)** · unter Stefan | Deploy, Bugs, Watchdog, Install nach OK |
| Markt / Tools / Wissen | **Radar (KI)** · WF14 · unter Stefan | Trends, OSS, APIs, Foren, Wochenreport, Install-Queue |

**Stefan** bestimmt Tempo. **Radar** sichtet Markt/Wissen. **Nils** schraubt nach Freigabe.  
Stefan: `docs/agency/stefan.md` · Nils: `docs/agency/nils.md` · Radar: `docs/agency/trend-scout.md`

**Wichtig ehrlich:** Cursor-Chat schläft ohne Eingabe. Dauerhaft wach: **Server-Cron + Watchdog + (optional) Cursor Automation** für Digests.

---

## Stellenplan – Phasen

### Phase A · Solo + KI (jetzt, Umsatz starten)

| # | Rolle | Wer | Stunden/Woche | Aufgabe | Gehalt / Kosten |
|---|-------|-----|---------------|---------|-----------------|
| 1 | Inhaber / Vertrieb / Gesicht | **Christian** | 25–40 | Akquise-Calls, Angebote, Kunden-Beziehung, Freigaben | Gewinn |
| 2 | Betriebsleiter / Treiber | **Stefan (KI)** · **aktiv** | „immer“ im Repo + Digests | Priorität, Tempo, Vorausschau, führt Team | Cursor + Automation |
| 3 | Ops / Plattform / Nachtwache | **Nils (KI)** · unter Stefan | „immer“ auf Server | Deploy, Bugs, Watchdog, Integrationen, Reports | Strom + Cursor + Server |
| 3b | Vertrags-Vorprüfung | **Anwalt (KI)** · WF10 | bei Verträgen / AVV | Checkliste Haftung–DSGVO–Geld–Leistung | Cursor Skill |
| 3c | Texter / Lektor / Design | **KI** · WF6–8 | Content | Copy + Lektor + Design-Prompts | Cursor Skills |
| 3d | Router | **KI** · WF1 | gemischte Aufträge | Intent → Mitarbeiter | API + n8n |
| 4 | Steuer / Formalia | Steuerberater (extern) | nach Bedarf | USt, Jahresabschluss | marktüblich |
| 4b | Rechtsfreigabe Großkunde | Anwalt (Mensch, extern) | vor Enterprise | Gegenlesen AVV/AGB/Sonderverträge | Honorar |

**Keine Festanstellung nötig**, bis wiederkehrender MRR da ist (Richtwert: 3–5 zahlende Kunden oder ~2–3k € MRR stabil).

### Phase B · Erste Menschen (wenn Geld fließt)

| # | Rolle | Profil | Wann | Kernjob |
|---|-------|--------|------|---------|
| 4 | Kundenservice / Krisen | Teilzeit, deutsch, ruhig am Telefon | ab Kunde 2–3 | Tickets, „Portal down“, Onboarding-Hilfe |
| 5 | Content / Social (Gastro) | Freelancer 1–2 Tage/Woche | parallel IG-Pipeline | Posts freigeben, Stories, Vorher/Nachher |
| 6 | Sales Support | optional Student / Azubi | wenn Christian Calls nicht schafft | Qualifizieren, Termin buchen, CRM pflegen |

### Phase C · Spezialisten (Skalierung)

| # | Rolle | Fokus |
|---|-------|--------|
| 7 | Ads / Meta | nur wenn Funnel + Landing pro Nische steht |
| 8 | Automation Engineer (Mensch) | n8n/komplexe Kunden, Nils entlasten |
| 9 | Designer (Retainer) | Marken, Flyer, Angebot-PDFs, Reel-Cover |

---

## Rollen-Steckbriefe (Was jede Position wirklich tut)

### 1. Christian – Inhaber & Sales

- Verkaufsgespräche, Vertrauen, Preis
- Letzte Freigabe: Mails an Kunden, Ads-Budgets, neue Server-Käufe
- Seminare moderieren
- **Nicht** den ganzen Tag Tickets und Server

### 2. Stefan – Betriebsleiter & Treiber (KI)

- Priorität und Tempo für das ganze Team
- Vorausschau (Engpässe, nächste 30–90 Tage)
- Briefings an Nils und künftige Rollen
- Christian entlasten: eine klare #1 statt Chaos
- Sheet: `docs/agency/stefan.md`

### 3. Nils – Ops & Radar (KI, unter Stefan)

Täglich / wöchentlich:
- Server, APIs, n8n, Deploy
- Trend-Radar: neue LLMs, Open-Source, Design-/Video-Tools, was für Webschmiede passt
- Report: „Das können wir ab jetzt anbieten“
- Vorschläge installieren **nur nach Freigabe** (außer klar harmlos/lokal)

### 3b. Anwalt – Vertrags-Vorprüfung (KI, unter Stefan)

- Vier Durchgänge: Haftung, DSGVO/AVV, Geld/Laufzeit, Leistung/Formalia
- Ausgabe: Ampel + Findings-Tabelle (keine „nochmal schauen“-Schleife ohne Checkliste)
- Sheet: `docs/agency/anwalt.md` · Skill: `.cursor/skills/anwalt/`
- Kein Ersatz für externen Anwalt bei Großkunden

### 4. Kundenservice / Krisen (Phase B)

- Erste Linie wenn Hassan schreibt „geht nicht“
- Checkliste: Portal, Drucker, Online-Schalter, DNS
- Eskalation an Nils/Christian
- Abend-Digest schon vorbereitet (Inbox-Agent)

### 5. Content / Social

- Branchen-Instagram (erst Gastro)
- Queue: KI entwirft, Mensch gibt frei
- Kein Auto-Engagement auf fremden Profilen (Vision)

### 6. Ads

- Erst wenn: Landing + Angebot + Tracking stehen
- Sonst verbranntes Geld

---

## Team nach Themen (nicht nach Jobtitel-Mode)

| Thema | Heute | Nächste Stufe |
|-------|-------|---------------|
| Website / Portal | Christian + Nils | Template-Bank pro Branche |
| Automation | Nils + n8n | Automation Engineer |
| SMS / CRM | eigenes System | Kundenservice pflegt Kontakte |
| Instagram / Video | geplant | Content-Freelancer + Pipeline |
| Ads | nein | nach Funnel |
| Sales | Christian | Sales Support |
| Krisen | Stefan steuert, Nils fix, Christian bei Eskalation | Kundenservice |
| Buchhaltung | Christian + Lexware-Pfad | Steuerberater |
| Voice | Demo self-host / Retell Kunden | Nils betreibt |

---

## Was wir **mehr anbieten** können (Produktliste für Verkauf)

Schon baubar / teilweise live:
1. Online-Bestellen + Admin (Gastro-Referenz SHY001)
2. CRM + Follow-up (SMS sobald Key)
3. Agency-Inbox (FAQ + Queue + Abend-Briefing)
4. Seminare + Cal.com-Termine
5. Akquise-Reports (Nacht-Scan)
6. Voice-Demo für Akquise-Gespräche
7. Onboarding-Mails + Setup-Portal

Als Nächstes verkaufbar machen:
8. Instagram-Post-Pipeline mit Freigabe
9. Branchen-Landing `/gastro` mit Wizard + Forecast
10. Meta-Ads nur mit klarem Paket „Testbudget + Landing“
11. Monatliches „Ops-Abo“: wir wachen über Portal + Automationen

---

## Trend-Radar (Hintergrund, ohne Blind-Install)

**Ziel:** Nils weiß, was neu und stark ist – du bekommst einen Report, kein Chaos auf dem Server.

| Takt | Was | Output |
|------|-----|--------|
| Wöchentlich | Scan: LLM/APIs (gratis/OSS), Design, Video, Social-Tools | `docs/agency/reports/YYYY-MM-DD-radar.md` |
| Wöchentlich | Mail/Briefing an dich: Top 5 + „für uns relevant?“ | E-Mail an Owner |
| Monatlich | Was wir **neu verkaufen** können | Update Stellenplan + Angebote |

**Regel Betriebssicherheit:** Nichts „extrem Mächtiges“ wird wild installiert. Ablauf immer:

1. Radar findet Kandidat  
2. Report an dich  
3. Du sagst ja/nein  
4. Nils installiert + Smoke-Test + Watchdog wenn nötig  

---

## Mitarbeiter-Sheet (Einstellungs-Priorität)

Wenn du jemanden suchst, in dieser Reihenfolge:

1. **Kundenservice Teilzeit** (deutsch, WhatsApp/Telefon, Stressfest)  
2. **Content Freelancer Gastro** (2 Reels/Woche + Freigabe)  
3. **Sales Support** (Termine + Nachfassen)  
4. Ads erst danach  

Pro Person: 1 Seite Aufgaben, Probezeit 3 Monate, Zugang nur zu dem was nötig (kein Root).

---

## Nächste konkrete Schritte (Geld verdienen)

1. **1–2 neue Gastro-Kunden** hinter SHY001 (Referenz verkaufen)  
2. Paket „Portal + Betreuung“ monatlich klar bepreisen  
3. Radar-Report freitags aktivieren (Cron oder Cursor Automation)  
4. Erste Stellenanzeige Kundenservice entwerfen, wenn MRR da  

---

## Dateien

- Dieser Plan: `docs/agency/mitarbeiter-stellenplan.md`
- Stefan (Betriebsleiter): `docs/agency/stefan.md`
- Handbuch Nils: `docs/agency/nils.md`
- Radar-Vorlage: `docs/agency/trend-scout.md`
- Paket-Entwurf: `docs/agency/paket-portal-ops-entwurf.md`
- Vision (Produkt): `docs/webschmiede-vision.md`
