# Verzeichnis von Verarbeitungstätigkeiten (Art. 30 DSGVO)

**Verantwortlicher:** Christian Kummetat, Webschmiede – digitale Handwerkskunst  
**Adresse:** Meinertzhagener Str. 16, 53894 Mechernich, Deutschland  
**E-Mail:** info@digitalehandwerkskunst.de · **USt-IdNr.:** DE370109681  
**Stand:** 22. Juli 2026  
**Internes Dokument – nicht veröffentlicht**

> Keine Rechtsberatung. Vorbehaltlich Anpassung bei neuen Diensten oder Mandanten.

---

## VVT-1: Betrieb der Agentur-Website (digitalehandwerkskunst.de)

| Feld | Inhalt |
|------|--------|
| **Zweck** | Bereitstellung der Unternehmenswebsite, Kontaktanbahnung B2B |
| **Rechtsgrundlage** | Art. 6 Abs. 1 lit. f DSGVO (berechtigtes Interesse); lit. b bei Vertragsanfragen |
| **Betroffene** | Website-Besucher, Interessenten |
| **Datenkategorien** | IP-Adresse, User-Agent, URL, Zeitstempel; ggf. Name, E-Mail, Firma bei Formularen; lokale Einwilligung `ws_cdn_consent` (kein Server-Cookie) |
| **Empfänger** | Hetzner (Hosting); Bunny Fonts / Cloudflare cdnjs **nur nach Einwilligung** |
| **Drittland** | Cloudflare/cdnjs: ggf. USA – SCC |
| **Löschfrist** | Server-Logs 14 Tage; Formulardaten siehe VVT-2/3 |
| **TOMs** | TLS, Hetzner DE, Nginx, Zugriffskontrolle SSH/2FA – siehe AVV Anlage 1 |

---

## VVT-2: Support-Tickets (Website-Formular, n8n)

| Feld | Inhalt |
|------|--------|
| **Zweck** | Bearbeitung von Support- und Störungsanfragen B2B-Kunden |
| **Rechtsgrundlage** | Art. 6 Abs. 1 lit. b, lit. f DSGVO |
| **Betroffene** | Kunden, Ansprechpartner |
| **Datenkategorien** | Name, E-Mail, Firma, Telefon, Betreff, Nachricht, Priorität, Zeitstempel |
| **Empfänger** | n8n (self-hosted Hetzner), Agency Brain CRM (intern), Telegram (interne Benachrichtigung) |
| **Drittland** | Telegram (VAE/global) – SCC, nur soweit für Benachrichtigung nötig |
| **Löschfrist** | Ticket erledigt → Archiv max. 24 Monate; Telegram spätestens 90 Tage; n8n-Logs 7 Tage |
| **TOMs** | HTTPS-Webhooks, n8n-Verschlüsselung, Mandantentrennung Docker |

---

## VVT-3: Projekt-/Preisanfragen (E-Mail, WhatsApp, Support)

| Feld | Inhalt |
|------|--------|
| **Zweck** | Bearbeitung von Interessenten- und Kundenanfragen (Preise auf Anfrage) |
| **Rechtsgrundlage** | Art. 6 Abs. 1 lit. b bzw. lit. f DSGVO |
| **Betroffene** | Interessenten, Kunden |
| **Datenkategorien** | Kontaktdaten, Nachrichteninhalt, ggf. Projektbeschreibung |
| **Empfänger** | intern (E-Mail/Telegram/Support); keine öffentliche Preisliste mehr |
| **Drittland** | Nein (soweit EU-Provider) |
| **Löschfrist** | bis Erledigung; Archiv max. 12 Monate |
| **TOMs** | Zugriffsbeschränkung, TLS |
| **Hinweis** | Öffentlicher Preis-Kalkulator und `/angebote.json` wurden entfernt (Juli 2026) |

---

## VVT-4: Vertragsabschluss und E-Signatur (DocuSeal)

| Feld | Inhalt |
|------|--------|
| **Zweck** | Erstellung, Versand, Unterzeichnung von B2B-Verträgen (Auftrag, AGB, AVV) |
| **Rechtsgrundlage** | Art. 6 Abs. 1 lit. b DSGVO |
| **Betroffene** | Vertragspartner (Unternehmer) |
| **Datenkategorien** | Name, E-Mail, Vertragsinhalte, Signatur, Zeitstempel, IP (DocuSeal-Standard) |
| **Empfänger** | DocuSeal self-hosted auf Hetzner DE |
| **Drittland** | Nein (self-hosted DE) |
| **Löschfrist** | Vertragslaufzeit + handels-/steuerrechtliche Fristen (6–10 Jahre) |
| **TOMs** | AVV mit DocuSeal, TLS, Backups DE |

---

## VVT-5: Kundenprojekte / Managed Services (Auftragsverarbeitung)

| Feld | Inhalt |
|------|--------|
| **Zweck** | Betrieb von Bestellportalen, n8n-Automation, CRM, Messaging für Kunden |
| **Rechtsgrundlage** | Art. 28 DSGVO (AVV); beim Kunden Art. 6 lit. b/a für Endkunden |
| **Betroffene** | Endkunden der Mandanten (Gäste, Leads, Anrufer) |
| **Datenkategorien** | Kontaktdaten, Bestellungen, Kommunikation, Metadaten – projektabhängig |
| **Empfänger** | Hetzner, ggf. Meta/WhatsApp, seven.io, Stripe, OpenAI/Requesty (optional) – siehe AVV Anlage 2 |
| **Drittland** | Je nach gebuchtem Dienst (Meta, OpenAI) – SCC/DPA |
| **Löschfrist** | AVV §8: **30 Tage** nach Vertragsende/Weisung (+ max. 30 Tage Backup-Rotation); n8n-Logs 7–14 Tage |
| **TOMs** | AVV Anlage 1 (TOMs), Docker-Mandantentrennung, 2FA, Backups |

**Hinweis:** Für jedes Kundenprojekt kann eine Ergänzung mit Mandantenname und konkreten Diensten geführt werden.

---

## VVT-6: E-Mail-Kommunikation

| Feld | Inhalt |
|------|--------|
| **Zweck** | Geschäftskommunikation, Vertrags- und Support-Korrespondenz |
| **Rechtsgrundlage** | Art. 6 Abs. 1 lit. b, lit. f DSGVO |
| **Betroffene** | Kunden, Lieferanten, Interessenten |
| **Datenkategorien** | E-Mail-Adresse, Name, Inhalt, Metadaten |
| **Empfänger** | E-Mail-Provider (je nach Setup), Empfänger |
| **Drittland** | Nur wenn Provider außerhalb EU – dann dokumentieren |
| **Löschfrist** | Geschäftsrelevant: bis 10 Jahre steuerrechtlich; sonst nach Zweckerfüllung |
| **TOMs** | TLS, sichere Passwörter, 2FA wo möglich |

---

## VVT-7: Buchhaltung / Rechnungswesen

| Feld | Inhalt |
|------|--------|
| **Zweck** | Rechnungsstellung, Erfüllung steuerrechtlicher Pflichten |
| **Rechtsgrundlage** | Art. 6 Abs. 1 lit. c, lit. b DSGVO |
| **Betroffene** | Kunden, Lieferanten |
| **Datenkategorien** | Name, Adresse, USt-Id, Rechnungsdaten, Zahlungsinformationen |
| **Empfänger** | Steuerberater (falls beauftragt), Finanzamt (gesetzlich) |
| **Drittland** | Nein, soweit nicht anders vereinbart |
| **Löschfrist** | 6–10 Jahre (HGB/AO) |
| **TOMs** | Zugriffsbeschränkung, Verschlüsselung, Backups |

---

## Gemeinsame technische und organisatorische Maßnahmen

Verweis auf **AVV Anlage 1** (`docs/agency/vertraege/04-avv-*.html`):

- Hosting Hetzner DE, ISO 27001
- SSH-Keys, 2FA, Passwort-Manager
- TLS 1.3, Verschlüsselung at Rest (DB, n8n Credentials)
- Nächtliche Backups DE
- n8n Log-Pruning (EXECUTIONS_DATA_PRUNE)
- Docker-Mandantentrennung pro Kunde

---

## Auftragsverarbeiter (Übersicht)

| Dienstleister | Funktion | AVV/DPA | Standort |
|---------------|----------|---------|----------|
| Hetzner Online GmbH | Hosting | Art. 28 AVV | DE |
| DocuSeal (self-hosted) | E-Signatur | Art. 28 AVV | DE |
| Meta Platforms | WhatsApp API (optional) | SCCs/DPF | EU |
| OpenAI Ireland (optional) | KI-API | DPA | EU/USA |
| seven.io (optional) | SMS | Art. 28 | DE |
| Stripe (optional) | Zahlung | SCCs | EU |
| Cloudflare (optional) | CDN | SCCs | EU |
| Telegram | Interne Support-Alerts | SCC | VAE/global |

---

## Änderungshistorie

| Datum | Änderung |
|-------|----------|
| 22.07.2026 | Erstversion: Website, Support, Kalkulator, DocuSeal, Mandanten, E-Mail, Buchhaltung |

---

**Nächste Pflege:** Bei neuem Subunternehmer, neuem Kundenprojekt oder neuem Formular diese Datei ergänzen und Datenschutzerklärung prüfen.
