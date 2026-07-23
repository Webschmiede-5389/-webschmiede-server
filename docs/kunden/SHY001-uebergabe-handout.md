# Übergabe & Handbuch — Snack House Yassine

**Kunde:** Hassan Yassine · Snack House Yassine  
**Projekt-Nr.:** SHY001  
**Erbracht von:** Webschmiede · Digitale Handwerkskunft  
**Stand:** Juli 2026  
**Status:** Testbetrieb (Live-Schaltung nach Freigabe)

---

> **Hinweis für Webschmiede:** Siehe `docs/kunden/README.md` und `docs/DIRECTION.md` (Onboarding-Befehl).

---

## 1. Übergabeprotokoll

| Punkt | Status |
|-------|--------|
| Marketing-Website | ✅ Bereitgestellt |
| Online-Bestellportal (56 Gerichte) | ✅ Bereitgestellt |
| Admin-Dashboard | ✅ Bereitgestellt |
| CRM & Kundenhistorie | ✅ Bereitgestellt |
| Aktionen / Rabatt-Engine | ✅ Bereitgestellt |
| Speisekarten-Verwaltung | ✅ Bereitgestellt |
| Drucker-Anbindung | ✅ Vorbereitet |
| DSGVO (Datenschutz, Impressum, Cookie-Hinweis) | ✅ Bereitgestellt |
| Server & Sicherheit (Firewall, Bot-Schutz) | ✅ Aktiv |
| SMS-Benachrichtigungen | ⏳ Wartet auf seven.io-Key |
| WhatsApp-Assistent (Preise/Texte per Chat) | ⏳ Vorbereitet, API-Anbindung offen |
| Eigene Domain + HTTPS | ⏳ Noch nicht verbunden |
| Stripe Online-Zahlung | ⏳ Noch nicht verbunden |

**Freigabe Kunde:** _________________________  **Datum:** _____________

---

## 2. Was Sie erhalten haben — Lieferumfang

### Öffentliche Seiten (für Ihre Gäste)

| Komponente | Was es bringt | Link (Test) |
|------------|---------------|-------------|
| **Startseite** | Professioneller Web-Auftritt: Speisekarte, Galerie, Öffnungszeiten, Lieferinfo, Kontakt | https://yassine.digitalehandwerkskunst.de/ |
| **Bestellportal** | Gäste bestellen 24/7 — Abholung oder Lieferung, Wunschzeit, Bar/EC/Stripe | https://yassine.digitalehandwerkskunst.de/bestellen |
| **Datenschutz & Impressum** | Rechtssicherheit (DSGVO), Cookie-Hinweis ohne Tracking | /datenschutz · /impressum |

### Admin-Bereich (nur für Sie)

| Tab | Funktion |
|-----|----------|
| **Bestellungen** | Eingehende Orders live · Status: Neu → Zubereitung → Unterwegs / Abholbereit → Fertig · Ton-Benachrichtigung |
| **Kunden** | Automatische Kundenkartei · Bestellhistorie · Notizen · Follow-up-Automation |
| **Bot-Log** | Protokoll aller WhatsApp-/Bot-Aktionen (wenn aktiv) |
| **Aktionen** | Zeitlich begrenzte Angebote (z. B. „Gratis Getränk ab 20 €“) — Countdown für Gäste sichtbar |
| **Speisekarte** | Preis, Text, Bild und Verfügbarkeit pro Artikel ändern — sofort im Bestellportal |
| **Drucker** | Bon-Druck: Browser, AutoPrint oder Netzwerkdrucker |

### Technik im Hintergrund (Webschmiede)

| Komponente | Nutzen für Sie |
|------------|----------------|
| **Eigener Server (Hetzner, DE)** | Schnelle Seite, keine Baukasten-Abhängigkeit, volle Kontrolle |
| **CRM-Datenbank** | Alle Kunden & Bestellungen bei Ihnen — kein externes CRM nötig |
| **Preis-Schutz** | Manipulierte Bestellpreise werden serverseitig abgelehnt |
| **Bot-Schutz (Honeypot)** | Automatische Spam-Bestellungen werden abgefangen |
| **Firewall & Login-Schutz** | Server abgesichert gegen Angriffe |
| **Automatisierung (n8n)** | Follow-ups, Backups, Healthchecks — im Hintergrund |
| **Jarvis-Bot (Vorbereitung)** | Später: Speisekarte per WhatsApp anpassen, ohne Anruf bei uns |

---

## 3. Ihre Zugänge

| Was | Wo / Wie |
|-----|----------|
| **Admin-Dashboard** | https://yassine.digitalehandwerkskunst.de/admin |
| **Admin-Passwort** | Separat übergeben (nicht per E-Mail) |
| **Support Webschmiede** | [Ihre Telefon/E-Mail eintragen] |
| **Bestellportal für Gäste** | Link „Jetzt bestellen“ auf Startseite oder direkt /bestellen |

> Nach Domain-Einrichtung: alle Links von `167.233.211.170` auf z. B. `www.snackhouse-mechernich.de` umstellen.

---

## 4. Kurzanleitung — Admin in 5 Minuten

### Bestellung bearbeiten
1. Admin öffnen → Tab **Bestellungen**
2. Neue Bestellung erscheint oben (Glockenton, wenn aktiviert)
3. Status anklicken: **Zubereitung** → **Unterwegs** (Lieferung) oder **Abholbereit** (Abholung) → **Fertig**
4. Optional: **Drucken** für Küchenbon

### Bestellungen pausieren (z. B. volle Küche)
- Oben rechts: Schalter **Online / Offline** — Gäste sehen dann eine Hinweis-Meldung

### Wartezeit anpassen
- Leiste unter dem Header: Minuten für Abholung / Lieferung → **Speichern**

### Aktion starten (z. B. Mittagsdeal)
1. Tab **Aktionen**
2. Titel, Beschreibung, Laufzeit, Gratis-Artikel oder Trigger wählen
3. **Aktion starten** — Countdown erscheint im Bestellportal

### Artikel ausverkauft oder Preis ändern
1. Tab **Speisekarte**
2. Artikel suchen → Verfügbarkeit, Preis, Text oder Bild anpassen
3. Speichern — sofort live für Gäste

### Tagesbericht
- Button **Tagesbericht** (Header): Umsatz, Anzahl Bestellungen, Top-Artikel

### Kunden & Bewertungen
1. Tab **Kunden**
2. Google-Review-Link eintragen (wenn vorhanden)
3. System sendet nach fertiger Bestellung automatisch Review-SMS (sobald SMS aktiv)
4. Inaktive Kunden erhalten Win-back-Nachricht nach 30 Tagen

---

## 5. Return on Investment — Was bringt Ihnen das?

> Die folgenden Zahlen sind **Beispielrechnungen** auf Basis typischer Gastronomie-Werte.  
> Ihre echten Werte sehen Sie im Admin unter **Tagesbericht**, sobald Bestellungen laufen.

### Qualitative Vorteile (sofort)

| Vorher | Nachher mit Webschmiede-System |
|--------|--------------------------------|
| Bestellungen nur telefonisch / über Portale | **Eigener Kanal** — 24/7, ohne Warteschleife |
| Provision an Lieferportale (oft 13–30 %) | **0 % Provision** auf Bestellungen über Ihr Portal |
| Keine Kundendaten | **Eigene Kundenliste** — wiederholbare Umsätze |
| Google-Bewertungen zufällig | **Automatische Review-Einladung** nach Bestellung |
| Speisekarte ändern = Aufwand | **Selbst ändern** im Admin (später auch per WhatsApp) |
| Kein professioneller Web-Auftritt | **Eigene Marke** — Snack House, nicht „irgendein Eintrag“ |

### Beispielrechnung A — Ersparte Portal-Provision

Annahme: 80 Online-Bestellungen/Monat · durchschnittlich 22 € Warenkorb

| | Lieferportal (ca. 20 %) | Eigenes Portal |
|--|-------------------------|----------------|
| Monatsumsatz online | 1.760 € | 1.760 € |
| Abzug Provision | −352 € | **0 €** |
| **Netto für Sie** | **1.408 €** | **1.760 €** |

→ **+352 €/Monat** bei dieser Annahme — fließt bei Eigenkanal voll bei Ihnen.

### Beispielrechnung B — Mehr Umsatz durch Verfügbarkeit

Annahme: 5 Bestellungen/Woche, die früher verloren gingen (besetzt, keiner geht ran)

| | Pro Jahr |
|--|----------|
| 5 × 22 € × 52 Wochen | **≈ 5.720 €** zusätzlicher Umsatz |

### Beispielrechnung C — Google-Bewertungen

| Mehr Bewertungen | Effekt |
|------------------|--------|
| +20 sichtbare Reviews/Jahr | Besseres Ranking bei „Döner Mechernich“ |
| Höhere Sternebewertung | Studien: +5–9 % Umsatz bei lokalem Geschäft (je nach Ausgangslage) |

### Beispielrechnung D — Zeitersparnis

| Vorgang | Ersparnis |
|---------|-----------|
| 3 Min. weniger Telefon pro Online-Bestellung × 80/Monat | **≈ 4 Stunden/Monat** |
| Kein manuelles Notieren von Adressen | Weniger Fehlbestellungen |

### Kennzahlen, die Sie selbst messen können

| KPI | Wo ablesen |
|-----|------------|
| Bestellungen heute | Admin → Tagesbericht |
| Umsatz heute | Admin → Tagesbericht |
| Beliebteste Gerichte | Admin → Tagesbericht (Top 5) |
| Lieferung vs. Abholung | Admin → Tagesbericht |
| Stammkunden | Admin → Kunden |
| Wirkung einer Aktion | Vergleich Tagesbericht vor/nach Aktion |

---

## 6. Was noch von Ihnen benötigt wird

| Punkt | Warum | Aufwand |
|-------|-------|---------|
| **Handynummer für SMS** | Bestellbestätigungen & Review-SMS | 2 Min. |
| **seven.io Account** (oder wir richten ein) | SMS-Versand | ca. 5 Min. |
| **Google Review Link** | Automatische Bewertungsanfragen | 5 Min. |
| **Domain wählen** (z. B. snackhouse-mechernich.de) | Professionelle URL, Vertrauen | Einmalig |
| **Stripe-Account** (optional) | Online-Vorauskasse | ca. 30 Min. |
| **Eigene Speisefotos** | Höhere Conversion im Bestellportal | 1–2 Std. Foto-Shooting |
| **Testbestellung durchführen** | Alles einmal durchspielen | 10 Min. |
| **Freigabe Go-Live** | Schalter auf „Online“ lassen | 1 Klick |

---

## 7. Optionale Erweiterungen (wenn alles stabil läuft)

> Kein Muss — erst sinnvoll, wenn das Basis-System im Alltag läuft und Sie zufrieden sind.

| Paket | Inhalt | Typischer Nutzen | Empfohlen wenn … |
|-------|--------|------------------|------------------|
| **🌐 Domain & SSL** | Eigene Adresse, HTTPS, Google-Sitemap | Vertrauen, besseres Google-Ranking | Sie live gehen wollen |
| **📱 SMS-Paket** | seven.io einrichten, Templates, Test | Gäste & Sie sofort informiert | > 20 Online-Bestellungen/Woche |
| **💬 WhatsApp-Assistent** | Speisekarte per Chat ändern („Döner heute +0,50 €“) | Änderungen ohne Admin-Login | Sie oft unterwegs sind |
| **💳 Stripe-Zahlung** | Online bezahlen vor Lieferung | Weniger „No-Shows“, schnellere Abwicklung | Viele Lieferbestellungen |
| **📸 Food-Fotoshooting** | Professionelle Bilder aller Top-Seller | +15–30 % Warenkorbwert (Branchendurchschnitt) | Conversion steigern |
| **⭐ Google-Optimierung** | Review-Link, Business-Profil, Local SEO | Mehr Laufkundschaft aus Google Maps | Weniger als 4,5 Sterne |
| **🖨️ Drucker vor Ort** | Thermodrucker einrichten & testen | Küche sieht Bons sofort | Viel Bestellvolumen |
| **📲 App auf Handy (PWA)** | „Snack House“ als Icon installierbar | Stammkunden bestellen schneller | Viele Wiederholer |
| **🎁 Treueprogramm** | Stempelkarte digital (z. B. 10. Bestellung gratis) | Wiederkehrrate +20–40 % | Stammkundenbasis da |
| **📣 Instagram-Automation** | Posts zu Aktionen & Gerichten (mit Freigabe) | Sichtbarkeit ohne täglichen Aufwand | Social Media wichtig |
| **🛡️ Wartung & Support** | Monatlich: Updates, Backup-Check, 2 h Support | Sie müssen sich um Technik nicht kümmern | Kein IT-Kopf im Team |
| **📊 Monatsreport** | PDF mit Umsatz, Top-Gerichte, Empfehlungen | Datenbasierte Entscheidungen | Mehrere Filialen / Wachstum |

**Empfohlene Reihenfolge:** Domain → SMS → Testbetrieb 4 Wochen → Stripe oder WhatsApp → Fotos → Treueprogramm

---

## 8. Support & Änderungswünsche

| Art | Beispiel | Wer |
|-----|----------|-----|
| **Selbst erledigen** | Preis ändern, Aktion starten, Artikel aus | Sie im Admin |
| **Webschmiede (klein)** | Text auf Startseite, neues Gericht | Support-Anfrage |
| **Webschmiede (Projekt)** | Zweite Filiale, neue Domain, App | Separates Angebot |

---

## 9. Checkliste Go-Live

- [ ] Testbestellung Abholung durchgeführt
- [ ] Testbestellung Lieferung durchgeführt
- [ ] Drucker getestet (optional)
- [ ] Admin-Passwort sicher notiert
- [ ] Google Review Link eingetragen
- [ ] SMS aktiviert (optional)
- [ ] Domain verbunden (optional)
- [ ] „Online“-Schalter auf **An**
- [ ] Link auf Google Business & Instagram gesetzt
- [ ] Freigabe unterschrieben

---

*Erstellt von Webschmiede · Digitale Handwerkskunft · webschmiede.de*  
*Technische Dokumentation (intern): `kunden/SHY001_snackhouse.json`*
