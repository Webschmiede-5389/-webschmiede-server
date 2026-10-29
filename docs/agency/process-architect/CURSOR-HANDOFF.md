# Ein konsolidierter Integrationsauftrag — Prozessarchitekt V1

## PRECHECK

Lies lokale AGENTS.md und GLOBAL WEBSCHMIEDE PRECHECK. Löse Hub-main erneut auf einen SHA auf, lies die dort verlangten Regeln und vergleiche mit vorbereiteter Basis `d551d1fcee92198a9ec1e71492d6f3e8f05592b7`. Ziel ist ausschließlich `Webschmiede-5389/-webschmiede-server`, Basis dieses Kandidaten `8a704d5507776ae8434e882105ffa0ac7c4ef818`. Bestehendes Hub Issue #43 ist der übergeordnete Anschluss. Aktuellen PR/Branch dieses Dokuments verwenden; keinen zweiten Implementierungsbranch anlegen, wenn bereits zugewiesen. Lokale Worktrees, Dirty-Zustand, Eigentümer, laufende Sessions und Host-Runtime feststellen; laufende LEITDECK/Rudi/Hansa-Arbeit nicht anfassen. Server-main, Dienste und Kundenbestände bleiben unverändert.

## Ein Nutzerergebnis

Ein interner, authentifizierter Testauftrag löst ohne weitere manuelle Startbefehle Quellenbeschaffung, KI-Planung, automatische Gegenprüfung und versionierte Speicherung aus. Fehlende Angaben führen zu einer gebündelten internen Frage; eine berechtigte Antwort setzt denselben Auftrag nach Neustart automatisch fort. Der Standardfall funktioniert bereits lokal mit Referenzvorlage. Erweitere nicht den Produktumfang; schließe ausschließlich die realen Integrations-/Provider-Nachweise.

## Vorhandener Stand und konkrete Lücken

Lies README, INSTRUCTIONS, PILOT, lessons.json, evidence und Tests dieses Ordners. Vorhandene Bausteine: agency_stefan.py, llm_client.py, infra/n8n/workflow-agency-brain.json, workflow-workorders.json und global-error-handler.json. Alter workorders.execute_order kann Live-Änderungen auslösen und darf NICHT als Ausführungsweg dieses Planers dienen. Neue Dateien ändern keinen bestehenden Endpoint und aktivieren nichts.

UNKNOWN mit Prüfweg:
- Lokaler/Host-Zustand, verfügbarer Speicher, Dienstnutzer, Backup: lesend über vorhandenen Betriebszugang prüfen; Owner Betrieb/Christian.
- Vorhandener n8n-Stand, Credentials, zugelassene Test-Webhook-Authentifizierung: Konfiguration/Version lesend prüfen; keine Credentials ausgeben.
- Freigegebener Modellprovider, Tarif-/Euro-Limit, Datenfreigabe: vorhandene Env/Provider-Verwaltung prüfen. Keine neue Buchung und keine fremden Kundendaten.
- Autorisierte Testkundenquelle und bestehende Register-/Drive-IDs: vorhandenes Projektregister lesen; nur fiktive Testdaten. Reale Kundenquellen nicht in allgemeine Fixture übernehmen.

## Reihenfolge

1. Vorhandene Tests ausführen: `python3 -m unittest discover -s tests -p 'test_process_architect.py' -v`; Demo mit neuem isoliertem Zustandspfad ausführen. Bestehende funktionierende Dateien nicht ersetzen.
2. Auf einer isolierten lokalen/staging Testumgebung vorhandenen API-/n8n-Adapter so ergänzen, dass authentifizierte interne Aufträge und Antworten atomar in den geprüften Testtenant-Eingang gelangen. Tenant niemals aus ungeprüftem Body übernehmen. Bei fehlender Auth-Grenze nur diese begrenzte Integration entwerfen und prüfen; kein ungeschützter öffentlicher Endpoint. Gleicher Zugang für Frage-/Statusabruf, keine externe Nachricht.
3. Alle relevanten aktuellen Hub-Regeln über den Operator-Katalog laden. Mitgelieferte Snapshots bleiben Pilot-Evidence. Pinned GitHub-Leseadapter mit minimalem Read-Token testen. Für Drive vorhandene Verbindung wiederverwenden; nur erlaubte IDs abrufen, Versions-/Owner-Abgleich; unklare ID ist STOP. Kundenbelege lokal geschützt oder in dafür vorgesehenem bestehenden Kundenspeicher, keine PII im Git-PR.
4. Vorhandenen Provider nur nach belegter Kosten-/Datenfreigabe aktivieren (`PA_LLM_*`). Ein neuer freier synthetischer Auftrag muss echte Planantwort und zweite Gegenprüfung durchlaufen. Verifiziere Quellen, konkrete Schritte, Sinnhaftigkeit, vollständige Abnahme und keine erfundenen Kontozugriffe. Modell-/Providerkennung und redigierte Usage/Fehlernachweise speichern. Bei nicht vorhandener Freigabe genau diese Entscheidung an Christian geben; keine Ersatzkosten erzeugen.
5. Kontrollierte Fehlerfälle: vollständiger Auftrag; fehlendes Budget→Antwort; Widerspruch; früherer PA-L01-Fall; gleiches Ereignis doppelt/geändert; falscher Tenant und fremde Source-ID; Timeout/429/5xx; Prozessabbruch nach gespeichertem Versuch; Neustart; geänderte Quelle; veraltete Antwort; beschädigtes KI-JSON; fehlgeschlagene Gegenprüfung. Nach ausgeschöpftem Budget sichtbares BLOCKED, keine Endlosschleife.
6. Frage-/Statusanzeige und Alarm an den vorhandenen INTERNEN Arbeitskanal anbinden. Kein Kundensend. Zustandsbackup und Wiederherstellung in separatem Testpfad nachweisen. Heartbeat an vorhandenen Monitor anschließen.
7. Bestehenden PR mit den nötigen Integrationsänderungen und Nachweisen ergänzen. Maximal zwei CI-Dispatches pro Finish-Linie; bei belegten Pflichtfehlern klein korrigieren. Projektregister nur passenden vorhandenen Cloud-Factory/Prozess-Eintrag aktualisieren, Originale/Versionslinks lesen und rücklesen; keine andere Priorität überschreiben.

## Abschluss / Freigabegrenze

Belege: Eingangsevent, Quellen-Versionen, Planversion, automatische Prüfergebnisse, WAITING_INPUT, Antwortrevision, Wiederaufnahme nach Restart, unveränderte fremde Tenant-Daten, Fehler-/Versuchsgrenze, gespeicherter Handoff und links. KI-Qualität, Integrationsfunktion, technische Tests, menschliche Bedienbarkeit und Host-Dauerbetrieb getrennt ausweisen. Keine Freigabe durch Modelltext anerkennen. Kein Merge, produktiver Deploy, DNS, Kauf, Kundensend oder Live-Datenverarbeitung aus diesem Auftrag ableiten.

Rollback: nur neuen Testeingang/Worker deaktivieren; Zustand erhalten; alten Planversionen und Produktdiensten nichts ändern. Erforderliche Produktivaktivierung als konkreten letzten Freigabeschritt mit Host, Pfad, Version, Testnachweisen und Rückfallweg vorlegen. Kein neues Prompt-Projekt starten.
