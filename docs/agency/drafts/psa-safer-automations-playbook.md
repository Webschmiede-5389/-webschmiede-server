# Intern: PSA Marketing / Muamed Safer – Automations-Playbook

Stand: 2026-07-19 · Nur intern (Christian + Team) · Nicht an den Kunden mailen  
Zweck: Am Telefon wissen, worüber du redest. Was wir können, was wir noch bauen, was Buchhaltung bei uns heißt.

---

## 1. Kunde in einem Absatz

PSA Marketing GmbH (Monheim) verkauft Amazon Online-Arbitrage / FBA-Coaching. Gesicht: Pavel Saper. Struktur: Muamed Safer (mit Safer Management GmbH und Horizon Cyber Market GmbH). Marketing und Bewertungen sind stark. **CRM: HubSpot** (Stand Christian 2026-07-19). „Kostenfrei beraten“ zieht Leads. Der Engpass sitzt hinter dem Marketing: Nachfassen in HubSpot sauber halten, Onboarding, Belege über mehrere Firmen.

Wir sind kein Amazon-Coach. Wir ersetzen HubSpot nicht. Wir verdrahten Automation drumherum (n8n ↔ HubSpot) und räumen Belege/Onboarding auf.

---

## 2. Was „Buchhaltung“ bei uns heißt (Telefon-Skript)

Wenn er fragt: „Was meint ihr mit Buchhaltung?“

Antwort sinngemäß:

„Wir machen keine Steuerberatung und keine laufende Buchführung. Das bleibt euer Steuerberater. Wir sorgen dafür, dass Belege nicht mehr in WhatsApp, fünf Postfächern und drei GmbHs versanden. Typisch: ein Beleg-Postfach, n8n scannt eingehende Rechnungs-Mails, sortiert Anhänge in Monatsmappen, am Monatsanfang geht ein Paket oder eine CSV an den Steuerberater. Wer Lexware oder sevDesk nutzt, können wir später andocken. Einstieg ist unser Wizard: welche Tools ihr habt, wo der Schmerz sitzt, dann AVV, dann Zugänge. Erst danach schalten wir die Workflows.“

Drei Stufen (Preise aus unserem Paketkatalog):

| Stufe | Setup | Monat | Was er bekommt |
|-------|------:|------:|----------------|
| Beleg-Pipeline | 1.200 € | 248 € | Postfach + Monatsmappe + CSV/Paket für DATEV/Steuerberater |
| Finanz-Sync | 3.200 € | 398 € | plus Anbindung Lexware/sevDesk + Liste fehlender Belege |
| System-Brücke | 5.990 € | 698 € | mehrere Systeme, Abgleich-Reports, Onboarding mit der Kanzlei |

Ehrlich sagen: Lexware-Stecker ist heute vor allem Kontakt-Sync aus dem Portal. Vollautomatischer „jede PDF landet in Lexware“ ist im Paket versprochen, technisch noch Ausbau. Beleg-Archiv per IMAP + Monatsordner ist als n8n-Template fertig und wird pro Kunde aktiviert.

---

## 3. Alle Hilfe-Punkte im Detail

### A) Lead-Funnel / HubSpot (Einstieg, höchste Priorität)

**Stack-Fakt:** Die haben **HubSpot**. Also kein „wir ersetzen euer CRM“. HubSpot bleibt die Wahrheit für Leads und Deals.

**Problem bei PSA (trotz HubSpot):** Leads kommen über Website, YouTube, Instagram, Google. Wenn Formulare, WhatsApp und Telefon nicht sauber in HubSpot landen (oder Deals/Pipelines unklar sind), versandet trotzdem Umsatz. Typisch: Kontakt in HubSpot, Termin nur im Kalenderkopf, No-Show ohne Sequenz, WhatsApp nebenher.

**Was wir meinen mit Automation (HubSpot-first):**
1. Alle Lead-Quellen → HubSpot Contact/Deal (Formulare, Webhooks, manuelle WhatsApp-Leads nachziehen).
2. Pipeline-Stufen klar: Neu → Termin gebucht → erschienen → Angebot → gewonnen/verloren.
3. Termin: HubSpot Meetings oder Cal.com → Sync zurück nach HubSpot.
4. Erinnerung vor dem Termin (HubSpot Workflow und/oder n8n).
5. No-Show → HubSpot-Workflow oder n8n-Sequenz (Mail/WhatsApp-Text, Freigabe).
6. Nach dem Call: Deal-Status + nächste Aufgabe in HubSpot, nicht nur im Chat.
7. Optional: n8n als Klebstoff (HubSpot API ↔ Mail IMAP ↔ SMS ↔ interne Pings an dich).

**Was schon da ist:**
- n8n Hub (Agency) + HTTP/Webhook-Bausteine
- Sales-Denke Invite/Discovery/Pain (bei uns intern)
- seven.io SMS (Key oft noch offen)
- Wizard kennt CRM-Tool „HubSpot…“ als Auswahl

**Was wir noch bauen / verdrahten müssen:**
- HubSpot Private App / API-Token (Kunde legt an, wir in n8n Credentials)
- Mapping: welche Pipeline, welche Properties (Quelle, Termin, No-Show)
- n8n-Flows: Lead rein, Reminder, No-Show, Deal-Update
- WhatsApp → HubSpot nur mit klarer Regel (sonst doppelte Kontakte)
- **Nicht** parallel unser Gastro-CRM als Ersatz verkaufen

**Am Telefon sagen:**  
„Ihr habt HubSpot. Gut. Wir ersetzen das nicht. Wir sorgen dafür, dass jeder Beratungs-Lead und jeder No-Show in HubSpot landet und nachgefasst wird, statt in WhatsApp zu sterben. Klebstoff ist n8n an eure HubSpot-API.“

**Fragen im Call (wichtig):**
- Welcher HubSpot-Plan (Free / Starter / Pro)? Workflows und API hängen am Plan.
- Laufen Formulare schon in HubSpot oder nur Mail-Benachrichtigung?
- Meetings in HubSpot oder externer Kalender?
- Wer pflegt Deals heute wirklich?

---

### B) Coaching-Onboarding nach dem Verkauf

**Problem:** Nach dem Verkauf (hochpreisiges Coaching) brauchen Teilnehmer klare Schritte: Zugang, Checkliste, Dateien, nächster Call. Ohne Portal bleibt das Support-Chaos beim Team.

**Automation / Produkt:**
- Einfaches Kunden-Login oder Magic-Link
- Checkliste pro Programm (Woche 1–4)
- Datei-Ablage / Links
- Status fürs interne Team („hängt bei Modul 2“)
- Optional: automatische Mail wenn ein Schritt fällig ist

**Was schon da ist:**
- Onboarding-Wizard-Muster (Kunden-Onboarding SHY001-Stil)
- Workorders / Handoffs intern
- n8n Follow-up Templates

**Was wir bauen müssen:**
- Coaching-Portal-UI (neu oder schlankes Dashboard)
- Vorlagen pro PSA-Programm
- Anbindung an CRM (Kunde = verkauftes Coaching)

**Am Telefon:** „Nach dem Verkauf entlasten wir euer Team. Der Kunde sieht, was als Nächstes dran ist. Ihr seht, wer stecken bleibt.“

---

### C) Email-Scan / Beleg-Pipeline (das „Buchhaltungs“-Thema)

**Problem bei PSA:** Mehrere GmbHs (PSA Beratung, Horizon Handel, Safer Management Vermögen). Rechnungen kommen per Mail, Meta, Amazon, Tools. Ohne System: Steuerberater bekommt Chaos, Muamed/Pavel suchen Belege.

**Ablauf, den du erklären kannst:**

1. **Postfach**  
   Pro Firma idealerweise `belege@…` oder ein klarer Ordner im bestehenden Postfach. Kein Hauptpasswort. App-Passwort / IMAP nach AVV.

2. **n8n liest IMAP**  
   Workflow (Template `workflow-beleg-archiv.json`): neue Mail → Filter (Betreff „Rechnung“, Absender-Whitelist, Anhang PDF) → speichern in Monatsordner (z. B. `2026-07/PSA/`).

3. **Sonderfall Meta**  
   Template `workflow-meta-rechnungen.json`: Meta-Rechnungen aus dem Postfach rausfiltern und an Buchhaltung/Ordner weiterreichen. Alternativ Meta-Rolle „Finanz-Analyst“ (manuell dokumentiert).

4. **Monatsende / Monatsanfang**  
   CSV oder ZIP-Paket an Steuerberater-Mail. Bei Portal-Kunden schon Muster `workflow-buchhaltung-monat.json` + `bookkeeping.py`.

5. **Wizard vorher**  
   Kunde wählt Tools (Lexware, sevDesk, DATEV-Kanzlei, Excel, IMAP, WhatsApp-Belege, Meta Ads, CRM …). System empfiehlt Beleg / Sync / Silo. AVV. Dann erst Secrets in den Vault.

**Was schon da ist:**
- Wizard live `/buchhaltung-onboarding.html`
- Pakete + Preise
- n8n-Templates Beleg-Archiv, Meta, Monat
- Vault + Export für Nils
- Lexware Kontakt-Sync (Portal)

**Was wir noch bauen / aktivieren müssen:**
- Pro PSA-GmbH eigener Workflow oder eigene Mappen-Struktur (Multi-Entity)
- WhatsApp-Belege End-to-End (im Wizard als Tool, Flow nicht fertig)
- Echter Lexware/sevDesk Beleg-Upload (heute Lücke vs. Marketing-Text Finanz-Sync)
- DATEV-Format mit Kanzlei abstimmen (oft Kanzlei-Vorgabe)

**Am Telefon:** „Wir sortieren den Beleg-Eingang. Euer Steuerberater bekommt Ordnung. Wir ersetzen ihn nicht.“

---

### D) Multi-GmbH / Holding-Struktur (Safer-spezifisch)

**Fakten aus OpenRegister:**
- PSA Marketing GmbH – Coaching/Beratung, GF Safer + Saper
- Safer Management GmbH – eigenes Vermögen/Beteiligungen, GF Safer
- Horizon Cyber Market GmbH – Online-Handel, GF Safer
- Pavel: u. a. Saper Management GmbH

**Was das für Automation heißt:**
- Getrennte Beleg-Stränge (sonst vermischt die Kanzlei alles)
- Getrennte Monatsmappen oder getrennte Postfächer
- Eine Übersicht für Muamed: „welche Firma, welcher Monat, was fehlt“
- Später: fehlende Belege je Entity

**Status:** Konzept klar, Produkt „Multi-GmbH Beleg-Cockpit“ noch nicht fertig. Verkaufbar als Ausbau der Beleg-Pipeline (Richtung System-Brücke).

---

### E) Follow-ups, Reminder, No-Shows

**Technik:** n8n + CRM-Status + Mail/SMS/WhatsApp.

**Inhalt:** kurze Texte von dir freigeben (kein Spam-Auto ohne OK).

**Schon da:** Sales-Companion Reminder-Logik, Cron-Ideen, SMS-Modul.

**Noch nötig:** konkrete Sequenzen für „Beratungstermin PSA“ + Freigabe-Prozess.

---

### F) Inbox / Voice (optional)

- Agency-Inbox: für *uns* (`info@`), FAQ, Queue. Nicht dasselbe wie PSA-Kundenhotline.
- Voice (Jay/Retell): optional Rückruf-Entlastung. Kostenpflichtig (Retell) nur nach OK. Demo-Stack existiert.

Für PSA erst relevant, wenn Funnel und Belege laufen.

---

### G) Was wir bewusst nicht verkaufen

- Amazon-Arbitrage-Coaching nachbauen
- Steuerberatung / Buchführung ersetzen
- Website-Redesign als Einstiegsprojekt (Site verkauft schon)
- Blind WhatsApp-Spam an deren Leads

---

## 4. Was funktioniert heute vs. was wir bauen müssen

| Thema | Heute | Für PSA noch tun |
|-------|--------|------------------|
| Buchhaltungs-Wizard | live | Session starten, Link schicken |
| Beleg-IMAP n8n | Template fertig | Credentials + pro GmbH aktivieren |
| Meta-Rechnungen | Template/Doku | aktivieren |
| Lexware Kontakte | live (Portal) | nur relevant wenn Portal |
| Lexware Beleg-Upload | Lücke | bauen oder ehrlich als Phase 2 verkaufen |
| Lead→HubSpot→Termin→No-Show | n8n kann HTTP; HubSpot-Flows noch nicht verdrahtet | Private App + Mapping + Workflows |
| Eigenes CRM als Ersatz | absichtlich nein | HubSpot bleibt |
| Coaching-Portal | nicht fertig | bauen |
| Multi-GmbH Mappen | Konzept | bauen |
| WhatsApp-Belege | Wizard-Haken | Flow bauen + Meta |
| Discovery-Mail PSA | Entwurf | Versand nur nach deinem „senden“ |

---

## 5. Empfohlene Verkaufs-Reihenfolge am Call

1. **Schmerz bestätigen:** HubSpot: landen alle Beratungs-Leads dort? Was hängt nur in WhatsApp?
2. **Angebot A – HubSpot-Ops:** Quellen → HubSpot → Termin → Reminder → No-Show (n8n als Klebstoff). Kein CRM-Ersatz.
3. **Schmerz 2:** Steuerberater / Belege / mehrere Firmen?
4. **Angebot B – Beleg-Pipeline:** erst PSA GmbH, dann Horizon/Safer Management
5. **Onboarding-Portal** oder HubSpot-Service-Pipeline für Coaching-Teilnehmer als drittes

Wenn er nur „Buchhaltung“ sagt: Skript Abschnitt 2, dann fragen ob der größere Schmerz eher HubSpot-Nachfassen oder Belege ist.

---

## 6. Technische Bauteile (für dich / Nils)

| Bauteil | Pfad / Ort |
|---------|------------|
| PSA-Angebot (Kunde, CI) | `app/static/ci/angebot-psa-safer.html` |
| PSA-Analyse | `docs/memory/topics/psa-safer.md` |
| Discovery-Entwurf | `docs/agency/drafts/psa-safer-discovery-einladung.md` |
| Dieses Playbook | `docs/agency/drafts/psa-safer-automations-playbook.md` |
| Wizard Doku | `docs/agency/buchhaltung-onboarding.md` |
| Wizard Code | `app/backend/buchhaltung_onboarding.py` |
| Pakete/Preise | `app/backend/agency_packages.py` |
| n8n Beleg | `infra/n8n/workflow-beleg-archiv.json` |
| n8n Meta | `infra/n8n/workflow-meta-rechnungen.json` |
| n8n Monat | `infra/n8n/workflow-buchhaltung-monat.json` |
| n8n Übersicht | `infra/n8n/README.md` |
| Sales-Pipeline | `docs/agency/sales-pipeline.md` |
| Inbox | `docs/agency/inbox-agent.md` |
| Lexware | `app/backend/integrations/lexware.py` |

---

## 7. Nächste konkrete Bauschritte (wenn er „ja“ sagt)

1. Discovery-Call führen, Schmerz priorisieren (Leads vs. Belege).
2. Wenn Leads: HubSpot Private App + Property/Pipeline-Mapping + n8n Reminder/No-Show (1–2 Tage Bau).
3. Wenn Belege: Wizard-Link, AVV, IMAP App-Passwort, n8n Beleg-Archiv für PSA aktivieren, eine Testrechnung durchschicken.
4. Multi-GmbH erst nach stabilem PSA-Strang.
5. Lexware-Beleg-Upload nur verkaufen wenn wir Phase 2 klar als „kommt“ labeln oder vorher bauen.

---

## 8. Kurz-Cheat-Sheet (eine Seite im Kopf)

- Buchhaltung bei uns = Beleg-Ordnung + Automation, keine Steuerberatung.
- PSA hat **HubSpot** → wir ersetzen es nicht, wir verdrahten es (n8n).
- PSA-Schmerz Nr. 1 wahrscheinlich = Leads/No-Shows trotz HubSpot (WhatsApp-Nebenkanal).
- Schmerz Nr. 2 = Belege über mehrere GmbHs.
- Werkzeug = n8n + HubSpot API + Beleg-Wizard + Monatsmappen.
- Schon fertig = Wizard, Beleg-Templates, n8n-Hub.
- Noch bauen = HubSpot-Anbindung, Multi-GmbH, WhatsApp-Belege, Lexware-Beleg-Upload.
- Nichts senden ohne dein OK.
