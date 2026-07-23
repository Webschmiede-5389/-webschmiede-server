# Anwalt-Briefing: Webschmiede Vertragspaket (wasserdicht machen)

Stand: 2026-07-19  
Auftraggeber: Christian Kummetat · Einzelunternehmen · B2B only  
USt-IdNr.: DE370109681 · Meinertzhagener Str. 16, 53894 Mechernich  
Mail: info@digitalehandwerkskunst.de

## Auftrag an den Anwalt (bitte so formulieren)

Bitte prüfen und bei Bedarf redigieren Sie unser B2B-Vertragspaket (Auftrag, AGB, AVV) auf **deutschem IT-/Agenturrechts- und DSGVO-Niveau**, sodass wir es gegenüber Gewerbe- und Mittelstandskunden sowie perspektivisch Enterprise-Kunden einsetzen können.

Gewünscht:
1. Schriftliches Kurzgutachten (Risiken / Ampel)
2. Markierte Änderungsvorschläge (Track Changes oder klare Diff-Liste)
3. Freigabe-Formular: „für B2B-Agenturleistungen geeignet / mit Vorbehalten“

Budget-Hinweis (Christian trägt ein): ca. ____ € netto / Stundenkontingent ____

## Was wir verkaufen

Digitale Agenturleistungen: Kundenportale, CRM, Hosting, Automation (n8n), optional Messaging (SMS/WhatsApp), Voice, Onboarding, Dashboards.  
Kein GHL. Eigenes CRM. Server: Hetzner Cloud, Deutschland (Nürnberg), ISO 27001 beim Anbieter.

## Dokumente (Beilage)

| Datei | Inhalt |
|-------|--------|
| `docs/agency/vertraege/pdf/02-auftrag.pdf` | Dienstleistungsvertrag |
| `docs/agency/vertraege/pdf/03-agb.pdf` | AGB B2B (2 Seiten) |
| `docs/agency/vertraege/pdf/04-avv.pdf` | AVV Art. 28 + TOMs (2 Seiten) |
| HTML-Lesefassungen | `02-…html`, `03-…html`, `04-…html` im gleichen Ordner |
| Live-Signatur | DocuSeal Community: https://sign.digitalehandwerkskunst.de |

Optional: KI-Vorprüfung (keine Rechtsberatung) `pruefprotokoll-2026-07-19.md` – Stand vor/nach Nachschärfung beachten.

## Bitte besonders prüfen

1. **Haftungsklauseln AGB** – Deckel 12 Monate Netto, indirekte Schäden, Drittanbieter-APIs, Freistellung Kundeninhalte  
2. **Mängel / Nacherfüllung** – B2B-tauglich?  
3. **Preisanpassung** – 6 Wochen + Sonderkündigung >5 %  
4. **AVV Art. 28** – TOMs (Hetzner Frankfurt/Nürnberg), Löschung 30 Tage, Betroffenenrechte, Unterauftragsverarbeiter + Widerspruch, Drittland/SCC  
5. **Laufzeit / Verlängerung** – Mindestlaufzeit + unbestimmte Verlängerung  
6. **IP / Nutzungsrechte** – Frameworks vs. Kundenassets  
7. **Geheimhaltung** – 3 Jahre nach Ende  
8. **Gerichtsstand / B2B** – Einzelunternehmen vs. GmbH-Kunden  
9. Fehlt etwas Pflichtiges für Agentur + Hosting + personenbezogene Daten von Endkunden des Kunden?

### NEU: n8n-Automation & KI-Infrastruktur (bitte explizit prüfen)

10. **§ 1 Gegenstand:** Wir betreiben n8n als Workflow-Automatisierungstool im Auftrag des Kunden. Klausel: „isolierte, dedizierte Instanz der Workflow-Automatisierungssoftware n8n".
11. **§ 5 Subunternehmer:** Genehmigte Liste + 14-Tage-Widerspruchsfrist (kein Einzelgenehmigungsverfahren). Hauptanbieter: Hetzner (DE, ISO 27001), Requesty B.V. (EU, LLM-Gateway, Zero-Log).
12. **§ 5a KI-Modelltraining-Ausschluss:** Garantie dass übermittelte pbD nicht für Training/Verbesserung von KI-Modellen verwendet werden.
13. **TOMs Docker/n8n:** Mandantentrennung durch Docker-Container, TLS 1.3, Encryption at Rest (DB + n8n-Credentials), MFA/IP-Filter für Admin, tägliche verschlüsselte Backups an getrenntem DE-Standort.
14. **KI-Routing:** Sensible Daten lokal (eigene Server Frankfurt, 0 % Drittlandtransfer); unkritische via EU-Enterprise-APIs. Self-Hosted AI-Gateway (kein US-Cloud-Router).
15. **§ 8 Haftungsabgrenzung:** Kunde = Verantwortlicher, bestimmt Datenflüsse. Keine Haftung des Auftragsverarbeiters wenn Kunde eigenständig datenschutzwidrige Drittanbieter-APIs einbindet + Freistellung.

### Gewünschte Ausgabeformate

- Ausfüllbares PDF/Word-Dokument (Anlage zu Angeboten)
- Digitale Zustimmungsfassung (für Online-/Klickvereinbarung im Kundenportal)

## Was wir bewusst nicht wollen

- Verbraucherverträge / Widerrufsbelehrung B2C  
- US-Standard-ToS ohne DE-Recht  
- Unrealistische 100 %-SLA oder Umsatzgarantien  

## Nach Freigabe

Wir pflegen die freigegebenen Texte in DocuSeal und Repo ein. Bitte finale Word/PDF-Fassung oder klar kommentierte Dateien liefern.

---

**Hinweis intern:** Ohne diese externe Freigabe bleibt das Paket eine praxisnahe Vorlage, keine „wasserdichte“ Rechtsgarantie.
