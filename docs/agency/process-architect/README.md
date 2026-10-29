# Webschmiede Prozessarchitekt V1 — Implementierungskandidat

Stand 30.10.2026. Kein Produktivbetrieb. Bestehender Bezug: Hub Issue #43 (Cloud Factory), Erweiterungsort `Webschmiede-5389/-webschmiede-server`, bestehender Planer Stefan. Keine neue Plattform, kein neues SaaS und keine Änderung bestehender Produkt- oder Agentenregeln.

## Was tatsächlich funktioniert

Ein einmal gestarteter Python-Worker nimmt neue JSON-Aufträge aus einem geschützten Eingang auf, beschafft konfigurierte Quellen, ergänzt Angaben aus Quellen, stellt gebündelte Rückfragen als gespeicherten Status bereit, plant den Standardfall, prüft den Plan und speichert unveränderliche Planversionen. Antworten werden automatisch aufgenommen; derselbe Prozess läuft weiter. Ein Neustart verliert den Auftrag nicht. Der getestete Eingang ist ein **lokaler geschützter Dateieingang**, kein angeschlossenes Kundenformular.

Der vollständig geprüfte Referenzfall ist eng: **bestehenden Kunden eindeutig zuordnen und einen Ablage-/Übergabeplan für Projektregister + Google Drive erstellen**. Er verwendet eine aus dem Hub abgeleitete Vorlage, keine generative KI. `PLAN_READY` bedeutet maschinell geprüfter Plan im angegebenen Modus; niemals technische Umsetzung oder Kundenfreigabe.

Für freie Anforderungen sind vollständige KI-Anweisungen, ein Adapter zum vorhandenen `llm_client`, eine zweite KI-Prüfung und ein begrenzter Korrekturlauf implementiert. **Echter Modellaufruf und fachliche Qualität frei erzeugter Pläne sind NOT_TESTED.** Modellantworten in Unit-Tests sind explizite Testdoubles. Keine universelle Planungsqualität behauptet.

## Sofort reproduzierbarer Test

Im bestehenden Server-Repo (Linux/Python 3.10+; hier Python 3.12.14):

```bash
python3 -m unittest discover -s tests -p 'test_process_architect.py' -v
python3 scripts/process_architect_demo.py /tmp/webschmiede-pa-demo-NEU
```

Der zweite Befehl verlangt ein neues Zustandsverzeichnis. Er startet den Worker einmal, gibt zwei Aufträge ein, beobachtet PLAN_READY und WAITING_INPUT, beendet/startet ihn zur Neustartprüfung und gibt die fehlende Budgetantwort ein. Danach entstehen beide Pläne ohne erneuten Planungsbefehl. Es werden keine externen Dienste aufgerufen. Die vorhandenen `evidence/*.json` dokumentieren einen tatsächlich ausgeführten Lauf.

## Betriebsschnittstelle V1

```bash
python3 scripts/process_architect_worker.py \
  --config docs/agency/process-architect/pilot-config.json \
  --state /ABSOLUTER/GESCHUETZTER/TESTPFAD
```

Nur ein Worker je Zustandspfad (OS-Dateisperre). Der Adapter erstellt je konfiguriertem Tenant `inbox`, `processed`, `rejected`, `output`. Eingänge zuerst als `.tmp` schreiben, danach atomar nach `.json` umbenennen. Nicht zugängliche oder noch unvollständige Dateien nicht als JSON veröffentlichen. Der Operator-/n8n-Adapter muss den Tenant aus geprüfter Identität wählen, **nie ungeprüft aus dem Kundenformular**. Der Worker hat keinen öffentlichen Port und ist kein Authentifizierungsdienst. Kunden erhalten keinen direkten Dateisystem- oder DB-Zugriff.

Ereignisvertrag: `event_id`, `job_id`, `kind=intake|answer|revise`, `data`. Antworten/Revisionen benötigen `expected_revision`. Pflichtfelder: `goal`, `owner`, `systems`, `acceptance`, `budget`. Beispielaufträge und Antwort liegen daneben. Quellen können fehlende Pflichtfelder über `format=facts` ergänzen. Widersprüche stoppen. Ein geänderter Payload mit derselben Ereignis-ID wird abgelehnt.

Zustände: QUEUED → RUNNING → WAITING_INPUT / RETRY / BLOCKED / REVIEW_REQUIRED / PLAN_READY. Nur zulässige neue Ereignisse oder beobachtete Quellenänderungen starten Folgearbeit. Alte Planversionen werden niemals überschrieben. Eine alte Freigabe gilt nicht für eine neue Version. BLOCKED wird nach Operator-Korrektur durch ein neues `revise`-Ereignis fortgesetzt; kein automatisches Endlosprobieren.

## Quellen und Aktualisierung

Die mitgelieferten Quellen sind **versionierte, sanitisierte Pilot-Snapshots**, keine automatische Live-Synchronisierung von GitHub/Drive. Hub-Basis `d551d1fcee92198a9ec1e71492d6f3e8f05592b7`; Server-Basis `8a704d5507776ae8434e882105ffa0ac7c4ef818`. Sie ersetzen nicht die kanonischen Originale. Die Quelle `source-playbook.md` ist ein gekennzeichneter Auszug mit entfernten kundenspezifischen Ordner-IDs. `source-system-task.md` ist ein Snapshot des gleichnamigen Originaldokuments. Regeländerungen werden nie selbst angenommen.

Der produktive Operator-Katalog liegt außerhalb von Kundeneingängen und enthält erlaubte IDs, Scope, Klassifikation, Version, Original-URL und optional SHA256. `global` ist nur für vorher sanitisierte Inhalte erlaubt. Kundenquellen sind an genau einen Tenant gebunden. Pro Lauf werden maximal 120.000 Zeichen gelesen; einzelne Quelldateien maximal 120.000 Bytes. Lokale Quelldateien werden bei jedem Lauf neu gelesen. Änderungen an ungepinnten Kundenfakten erzeugen eine neue Planversion; Änderungen an gepinnten Regeln stoppen zur Prüfung.

Implementierter optionaler GitHub-Leseadapter: Source-Eintrag mit `transport=github`, `repository`, `repository_path`, `version=<40-stelliger Commit-SHA>`, `scope`, `classification`, `url`. Token nur über `PA_GITHUB_READ_TOKEN` (minimaler Contents-Read-Zugriff). Kein Zugriff auf frei übermittelte URLs, keine Redirects, keine Secret-Ausgabe. Dieser Adapter ist ohne Zugangsdaten **nicht live getestet**. Die Version ist pro Plan fest; neuere Hub-Stände werden erst nach gezieltem Preflight im Operator-Katalog freigegeben. Drive-Anbindung und Projektregister-Rückschreiben sind **INTEGRATION_OPEN**; keine Änderungen an echten Kundenquellen vorgenommen.

Erfahrungen: `lessons.json`, Eintragsschema `lesson-template.json`. PA-L01 ist eine neu reproduzierte Schwäche des vorhandenen `agency_stefan.plan_project`; PA-L02 ist eine Übertragung bestehender Nachweisregeln. Kein erfundener Kundenincident. Neue Erkenntnisse werden zunächst Vorschläge; keine automatische Änderung kanonischer Regeln. Eine automatische Extraktion beliebiger alter Chats ist nicht implementiert.

## KI-Konfiguration und Grenzen

Vorhandener Client wird wiederverwendet; kein neuer SDK und kein unkontrollierter Provider-Fallback. Erforderlich: `PA_LLM_APPROVED=1`, `PA_LLM_BASE_URL` (HTTPS), `PA_LLM_KEY`, `PA_LLM_MODEL`. Werte ausschließlich in geschützter Umgebung. Datenschutz-/Mandantenfreigabe und Tariflimit müssen vor echten Kundendaten feststehen. In diesem Auftrag wurde kein kostenpflichtiger Modellaufruf ausgeführt.

Je Revision höchstens 3 Versuche einschließlich Reparatur; jeder Versuch höchstens 2 Modellaufrufe (Plan + Gegenprüfung), maximal 6.000/1.500 Ausgabetoken und ein harter 50-Sekunden-Prozess-Timeout. Versuche werden vor Aufruf persistiert; Neustart setzt sie nicht zurück. Kontextgröße und Ausgabetoken sind begrenzt, ein finanzielles Euro-Limit muss zusätzlich am vorhandenen Provider eingerichtet werden. Auch ein abgebrochener Modellaufruf kann vom Provider berechnet werden. Kein Preis oder vorhandenes Guthaben wird behauptet.

Die maschinelle Gegenprüfung verwendet das konfigurierte Modell erneut; sie ist kein unabhängiges menschliches Review und kein Fehlerfreiheitsbeweis. Kritische fachliche Entscheidungen bleiben als UNKNOWN/REVIEW_REQUIRED offen. Strukturprüfungen allein beweisen weder Rechtskonformität noch technische Machbarkeit unbekannter Provider.

## Integration, Betrieb und Rückfallweg

Vorhandene n8n-Brücke und vorhandenen Error Handler nutzen. In diesem Kandidaten sind weder n8n importiert noch Endpunkte im produktiven Flask-System geändert. Der erste Adapter muss authentifizierte Aufträge/Antworten atomar in den geschützten Eingang schreiben und Ausgabe/Fragen dem vorhandenen internen Arbeitskanal zuordnen. Nicht einfach den bestehenden Workorders-Ausführungspfad aufrufen: dieser kann Live-Änderungen ausführen.

Vor Aktivierung auf vorhandenem AUTO-Host: Kapazität, Dienstnutzer/Dateirechte, persistenter separater Pfad, Backup/Restore, erlaubter Provider und Lesequellen prüfen. Keine gemeinsame Produkt-DB verwenden. Heartbeat-Datei durch vorhandenes Monitoring auf Alter prüfen; Fehler/Fragen werden bereits dauerhaft gespeichert, eine aktive Benachrichtigung ist noch nicht angeschlossen. State-Daten nicht ins Repo committen. Aufbewahrungsfrist für echte Kundendaten vor Live-Betrieb festlegen; V1 löscht nichts automatisch.

Rollback: Eingang deaktivieren, nur den dedizierten Planungsworker stoppen, SQLite und Ausgaben sichern, vorherigen Workerstand starten. Keine Kundenaktion rückgängig zu machen, weil dieser Baustein ausschließlich plant. Für SQLite-Backup den Worker sauber stoppen oder SQLite-Backup-API nutzen. Nach Restart denselben Auftrag prüfen; kein Reset der Ereignis- oder Versuchstabellen.

## Abnahmestatus

- Erstellt: Module, Worker, KI-Adapter/Anweisungen, Quellenkatalog, Erfahrungs-/Planvorlagen, Pilot, Tests, Integrationsauftrag.
- Lokal getestet: deterministischer Standardprozess, persistentes Warten/Fortsetzen, Neustart, Dubletten, Widersprüche, Quellenrechte/-änderungen, Begrenzung und Reparatur mit Modell-Testdouble.
- Nicht getestet: echter KI-Provider, freie Planqualität, Live-GitHub-Adapter, n8n-/Drive-/Formularverbindung, Host-Dauerbetrieb, echter Nutzertest.
- Nicht aktiviert, nicht gemergt, kein Deployment, keine Kundennachricht.

Genau ein nächster Schritt: den beigefügten `CURSOR-HANDOFF.md` im bestehenden Server-Spoke für isolierte Integration und echten Provider-Pilot ausführen. Produktivaktivierung erst nach konkreter Freigabe; dies ist kein neuer Produktauftrag.
