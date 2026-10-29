# Pilot: automatisch geplanter Kundenstart

Status: PLAN_READY für den engen deterministischen Referenzfall. Synthetische Kundendaten; keine echte Drive-Anbindung und kein KI-Provider-Test.

Ziel: Bestehenden Kunden eindeutig zuordnen und einen vollständigen Ablage- und Übergabeplan erzeugen

## Umfang
- Bestehender Kundenstart: Identität, Originale, Ablageplan, Abnahme und interne Übergabe

## Ausgeschlossen
- Keine Kundenordner anlegen oder migrieren
- Keine Kundenkommunikation, Werbung, Deployment oder Zahlung
- Keine allgemeine Branchenautomationsgarantie

## S1 — Kundenauftrag identifizieren

**audit:** Ereignis-ID, Kundenkennung, Quellen-ID/Version, Zustand und Prüfresultat; keine vollständigen Personendaten oder Secrets loggen.

**deduplication:** tenant_id + project_id + event_id eindeutig; gleiche ID mit anderem Inhalt STOP; Planrevision monoton.

**depends_on:** []

**failure:** Fehlende Identität, doppelte Registertreffer oder tenant-Mismatch: STOP ohne weitere Kundenquellen zu lesen.

**inputs:** {"event_id": "vom Eingang", "goal": "aus Auftrag", "project_id": "aus Projektregister", "tenant_id": "aus authentifiziertem Eingang"}

**mapping:** event_id→Ereignisschlüssel; tenant_id+project_id→Planungsauftrag

**output:** Gespeicherter Auftrag mit Version 1

**owner:** Verantwortlicher aus Auftrag; technischer Betrieb Webschmiede

**permissions:** Nur freigegebene Kundenkennung; Registerzeile, Drive-ID und Rechtsträger abgleichen. Leserechte vor Zugriff prüfen. Keine öffentliche Freigabe.

**preconditions:** Operator hat Planung erlaubt; Tenant-Bindung serverseitig gesetzt

**processing:** AUTOMATISCH: Eingang validieren; genau eine Registerzuordnung verlangen.

**recovery:** Letzten bestätigten Zustand laden; bereits bestätigte Schritte anhand Version prüfen. Unklare Schreibwirkung erst rücklesen. Historische Pläne erhalten.

**retry:** Lesefehler 429/5xx maximal 2 Wiederholungen nach 5s/30s; 401/403 sofort STOP. Kein blindes Wiederholen von Writes.

**system:** Projektregister + Google Drive

**test:** Identische Nachricht zweimal: ein Auftrag. Geänderte Nachricht unter gleicher ID: Konflikt; fremder Tenant: keine Ausgabe.

**trigger:** Freigegebener Auftrag eingegangen

## S2 — Bestand und Originale auflösen

**audit:** Ereignis-ID, Kundenkennung, Quellen-ID/Version, Zustand und Prüfresultat; keine vollständigen Personendaten oder Secrets loggen.

**deduplication:** tenant_id + project_id + event_id eindeutig; gleiche ID mit anderem Inhalt STOP; Planrevision monoton.

**depends_on:** ["S1"]

**failure:** Kein Ordner, falscher Parent oder mehrere Kandidaten: WAITING_INPUT mit Zuständigem und Prüfweg.

**inputs:** {"customer_folder_id": "verknüpfte Registerzeile", "owner": "freigegebener Ansprechpartner", "source_links": "Register-Originale"}

**mapping:** Register.customer_folder_id→Drive.file.id; Drive.parents→erwarteter Kundenstamm; Originalrevision→Quellenstand

**output:** Quellenliste mit IDs, Versionen und Berechtigungsbefund

**owner:** Verantwortlicher aus Auftrag; technischer Betrieb Webschmiede

**permissions:** Nur freigegebene Kundenkennung; Registerzeile, Drive-ID und Rechtsträger abgleichen. Leserechte vor Zugriff prüfen. Keine öffentliche Freigabe.

**preconditions:** S1 eindeutig; Lesezugriff vorhanden

**processing:** AUTOMATISCH NACH EINRICHTUNG: exakte Drive-ID und Elternordner rücklesen; vorhandene Briefings und Entscheidungen abrufen. Nicht nach ähnlichem Namen zuordnen.

**recovery:** Letzten bestätigten Zustand laden; bereits bestätigte Schritte anhand Version prüfen. Unklare Schreibwirkung erst rücklesen. Historische Pläne erhalten.

**retry:** Lesefehler 429/5xx maximal 2 Wiederholungen nach 5s/30s; 401/403 sofort STOP. Kein blindes Wiederholen von Writes.

**system:** Projektregister + Google Drive

**test:** Vorhandene korrekte ID wird wiederverwendet. Falscher Parent: kein Neuanlegen, keine Umbenennung.

**trigger:** S1 erfolgreich

## S3 — Pflichtangaben und Widersprüche klären

**audit:** Ereignis-ID, Kundenkennung, Quellen-ID/Version, Zustand und Prüfresultat; keine vollständigen Personendaten oder Secrets loggen.

**deduplication:** tenant_id + project_id + event_id eindeutig; gleiche ID mit anderem Inhalt STOP; Planrevision monoton.

**depends_on:** ["S2"]

**failure:** Veraltete Antwort: REVISION_CONFLICT. Kein Neustart des Gesamtprojekts; keine ungeprüfte Budgetannahme.

**inputs:** {"acceptance": "vereinbarter Auftrag", "budget": "freigegebene Aufwandgrenze", "goal": "Auftrag/Briefing", "owner": "Register", "systems": "Bestand"}

**mapping:** Fehlendes Feld→{field,UNKNOWN,owner,check}; Antwort.expected_revision→aktueller Auftrag

**output:** Vollständiges Briefing oder dauerhaftes WAITING_INPUT

**owner:** Verantwortlicher aus Auftrag; technischer Betrieb Webschmiede

**permissions:** Nur freigegebene Kundenkennung; Registerzeile, Drive-ID und Rechtsträger abgleichen. Leserechte vor Zugriff prüfen. Keine öffentliche Freigabe.

**preconditions:** Relevante Quellen aus S2 verfügbar

**processing:** AUTOMATISCH: Felder aus autorisierten Quellen ergänzen; Widerspruch nicht still priorisieren. MENSCHLICHE ENTSCHEIDUNG nur für ungelöste blockierende Angaben; eine gebündelte Rückfrage.

**recovery:** Letzten bestätigten Zustand laden; bereits bestätigte Schritte anhand Version prüfen. Unklare Schreibwirkung erst rücklesen. Historische Pläne erhalten.

**retry:** Lesefehler 429/5xx maximal 2 Wiederholungen nach 5s/30s; 401/403 sofort STOP. Kein blindes Wiederholen von Writes.

**system:** Projektregister + Google Drive

**test:** Ohne Budget keine Planfreigabe. Nach Antwort zur richtigen Revision automatisch weiter; veraltete Antwort unverändert ablehnen.

**trigger:** S2 erfolgreich

## S4 — Vorhandene Ablagestruktur abgleichen

**audit:** Ereignis-ID, Kundenkennung, Quellen-ID/Version, Zustand und Prüfresultat; keine vollständigen Personendaten oder Secrets loggen.

**deduplication:** tenant_id + project_id + event_id eindeutig; gleiche ID mit anderem Inhalt STOP; Planrevision monoton.

**depends_on:** ["S3"]

**failure:** Abweichender Name, Doppelung oder fehlender Pflichtordner: Entscheidung erforderlich; keine automatische Migration.

**inputs:** {"expected_names": ["01 · Kunde & Zusammenarbeit", "02 · Recherche & Strategie", "03 · Website & Landingpages", "04 · Werbung & Creatives", "05 · Präsentationen & Ergebnisse", "06 · Freigaben & Übergabe"], "folder_children": "Drive.list der geprüften Kunden-ID"}

**mapping:** Ordnername→bestehende Drive-ID; genau sechs kanonische Stammordner→Strukturprüfung

**output:** Ablageplan mit sechs Originalverweisen

**owner:** Verantwortlicher aus Auftrag; technischer Betrieb Webschmiede

**permissions:** Nur freigegebene Kundenkennung; Registerzeile, Drive-ID und Rechtsträger abgleichen. Leserechte vor Zugriff prüfen. Keine öffentliche Freigabe.

**preconditions:** S3 vollständig; genau ein bestehender Kunde

**processing:** AUTOMATISCH: sechs kanonische Unterordner prüfen und vorhandene IDs im Plan referenzieren. V1 plant ausschließlich; keinerlei Ordneranlage.

**recovery:** Letzten bestätigten Zustand laden; bereits bestätigte Schritte anhand Version prüfen. Unklare Schreibwirkung erst rücklesen. Historische Pläne erhalten.

**retry:** Lesefehler 429/5xx maximal 2 Wiederholungen nach 5s/30s; 401/403 sofort STOP. Kein blindes Wiederholen von Writes.

**system:** Projektregister + Google Drive

**test:** Sechs korrekte Ordner: null Neuanlagen; umbenannter Ordner 03: STOP für Änderung, Befund im Plan.

**trigger:** S3 erfolgreich

## S5 — Ablauf und Prüfungen erzeugen

**audit:** Ereignis-ID, Kundenkennung, Quellen-ID/Version, Zustand und Prüfresultat; keine vollständigen Personendaten oder Secrets loggen.

**deduplication:** tenant_id + project_id + event_id eindeutig; gleiche ID mit anderem Inhalt STOP; Planrevision monoton.

**depends_on:** ["S4"]

**failure:** Ungültiges KI-JSON oder unbelegte Quelle: begrenzte Korrektur, danach BLOCKED. Neue fachliche Anforderungen benötigen Entscheidung.

**inputs:** {"briefing": "S3", "folder_map": "S4", "lessons": "sanitisierte belegte Erfahrungen", "rules": "Hub am festgehaltenen SHA"}

**mapping:** Briefing→01; Strategie→02; Website-Originale→03; Creatives→04; Ergebnisse→05; Freigaben→06

**output:** Detaillierter versionierter Plan; UNKNOWN-Liste; Ausführungsauftrag

**owner:** Verantwortlicher aus Auftrag; technischer Betrieb Webschmiede

**permissions:** Nur freigegebene Kundenkennung; Registerzeile, Drive-ID und Rechtsträger abgleichen. Leserechte vor Zugriff prüfen. Keine öffentliche Freigabe.

**preconditions:** Keine blockierenden Widersprüche

**processing:** AUTOMATISCH: Originale den sechs bestehenden Bereichen zuordnen; pro Lieferung Ziel, Eingaben, Zustände, Fehlerpfade und Abnahme festhalten. KI nur für neue Interpretation, bestehende Regeln deterministisch anwenden.

**recovery:** Letzten bestätigten Zustand laden; bereits bestätigte Schritte anhand Version prüfen. Unklare Schreibwirkung erst rücklesen. Historische Pläne erhalten.

**retry:** Lesefehler 429/5xx maximal 2 Wiederholungen nach 5s/30s; 401/403 sofort STOP. Kein blindes Wiederholen von Writes.

**system:** Projektregister + Google Drive

**test:** Plan enthält alle Schritt-Felder, gültige Quellen und rückwärtsfreie Abhängigkeiten; alte ok=true-Antwort ohne Pflichtdaten wird nicht akzeptiert.

**trigger:** S4 erfolgreich

## S6 — Gegenprüfen und speichern

**audit:** Ereignis-ID, Kundenkennung, Quellen-ID/Version, Zustand und Prüfresultat; keine vollständigen Personendaten oder Secrets loggen.

**deduplication:** tenant_id + project_id + event_id eindeutig; gleiche ID mit anderem Inhalt STOP; Planrevision monoton.

**depends_on:** ["S5"]

**failure:** Speicherfehler: kein Erfolg. Alte Freigabe nicht auf neue Version übertragen.

**inputs:** {"acceptance": "S3", "plan": "S5", "source_manifest": "IDs/SHA/Datum"}

**mapping:** Plan.version→unveränderlicher Plan; source_sha→Herkunft; findings→gezielte Korrektur

**output:** Gespeicherter Plan mit maschinellem Prüfstatus; fachliche Freigaben separat

**owner:** Verantwortlicher aus Auftrag; technischer Betrieb Webschmiede

**permissions:** Nur freigegebene Kundenkennung; Registerzeile, Drive-ID und Rechtsträger abgleichen. Leserechte vor Zugriff prüfen. Keine öffentliche Freigabe.

**preconditions:** Plan gegen ursprüngliches Kundenproblem abgeglichen

**processing:** AUTOMATISCH: Struktur, Quellen, bekannte Fehler, Rechte, Retry/Dedupe und Abschlusskriterien prüfen. Planversion append-only speichern; aktuellen Status separat aktualisieren.

**recovery:** Letzten bestätigten Zustand laden; bereits bestätigte Schritte anhand Version prüfen. Unklare Schreibwirkung erst rücklesen. Historische Pläne erhalten.

**retry:** Lesefehler 429/5xx maximal 2 Wiederholungen nach 5s/30s; 401/403 sofort STOP. Kein blindes Wiederholen von Writes.

**system:** Projektregister + Google Drive

**test:** Nach Neustart gleiche Planversion vorhanden; Quellenänderung erzeugt neue Version oder sichtbaren Blocker; alte Bytes unverändert.

**trigger:** S5 erfolgreich

## S7 — Übergabe und kontrollierte Fortsetzung

**audit:** Ereignis-ID, Kundenkennung, Quellen-ID/Version, Zustand und Prüfresultat; keine vollständigen Personendaten oder Secrets loggen.

**deduplication:** tenant_id + project_id + event_id eindeutig; gleiche ID mit anderem Inhalt STOP; Planrevision monoton.

**depends_on:** ["S6"]

**failure:** Fehlende Live-Verbindung: INTEGRATION_OPEN, keine Aktivierungsmeldung.

**inputs:** {"blockers": "UNKNOWN-Liste", "execution_rights": "separate Freigabe", "plan_version": "S6"}

**mapping:** Planlink+Version→bestehender Projekteintrag; offene Frage→zuständiger Operator

**output:** Ausführungsbereiter Auftrag oder klarer einzelner Blocker mit Verantwortlichem

**owner:** Verantwortlicher aus Auftrag; technischer Betrieb Webschmiede

**permissions:** Nur freigegebene Kundenkennung; Registerzeile, Drive-ID und Rechtsträger abgleichen. Leserechte vor Zugriff prüfen. Keine öffentliche Freigabe.

**preconditions:** Gespeicherter Plan rückgelesen; Zuständigkeiten benannt

**processing:** AUTOMATISCH: vollständigen internen Auftrag bereitstellen. NACH FREIGABE: durch bestehende Integration Register aktualisieren. MENSCHLICH: Geschäftsentscheidung/Produktivfreigabe; kein automatischer Versand oder Deploy.

**recovery:** Letzten bestätigten Zustand laden; bereits bestätigte Schritte anhand Version prüfen. Unklare Schreibwirkung erst rücklesen. Historische Pläne erhalten.

**retry:** Lesefehler 429/5xx maximal 2 Wiederholungen nach 5s/30s; 401/403 sofort STOP. Kein blindes Wiederholen von Writes.

**system:** Projektregister + Google Drive

**test:** Ohne Live-Freigabe werden weder Nachrichten verschickt noch Ordner oder Produktivsysteme verändert.

**trigger:** S6 erfolgreich

## Übergabe
Zielrepo Webschmiede-5389/-webschmiede-server. Vorhandene Agency-/n8n-Brücke nutzen. Erst authentifizierten Eingang und erlaubte Quellen für Testtenant anbinden; Pilot nur lesend ausführen; Register-Writeback separat freigeben. Nach Tests genau eine kontrollierte Aktivierungsentscheidung. Keine neuen Produktworktrees berühren.

## Quellen
- local:docs/agency/process-architect/intake-template.json @ v1
- local:docs/agency/process-architect/lessons.json @ v1
- local:synthetic-pilot @ v1
- https://github.com/Webschmiede-5389/my-company-hub/blob/d551d1fcee92198a9ec1e71492d6f3e8f05592b7/knowledge/SOLO-OPERATOR-PLAYBOOK.md @ d551d1fcee92198a9ec1e71492d6f3e8f05592b7
- https://github.com/Webschmiede-5389/my-company-hub/blob/d551d1fcee92198a9ec1e71492d6f3e8f05592b7/core/SYSTEM-TASK.md @ d551d1fcee92198a9ec1e71492d6f3e8f05592b7
