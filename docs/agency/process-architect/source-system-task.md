# Webschmiede — SYSTEM > TASK

Stand: 2026-10-07
Status: CANONICAL

## Zweck
Vor jeder relevanten Lösung zuerst prüfen, ob das sichtbare Problem nur ein Symptom eines größeren Systemfehlers ist. Keine lokale Optimierung, wenn Source of Truth, Scope oder Entwicklungsprozess unklar sind.

## Pflichtprüfung vor jeder größeren Empfehlung
1. **Problemklasse** — lokal, wiederkehrend oder systemisch?
2. **Source of Truth** — welcher Commit, Branch/Worktree, Runtime und Deploy-Stand ist tatsächlich aktuell?
3. **Komplexität** — fügt die Lösung neue Regeln, Agenten, Abstraktionen, Tools oder Zustände hinzu? Kann stattdessen Scope entfernt werden?
4. **Produktwert** — ist die Änderung für den nächsten bezahlbaren Benutzerablauf nötig? Falls nein: Backlog.
5. **Evidenz** — reicht Gesprächskontext aus? Wenn aktueller Repo-/Runtime-Zustand verfügbar ist, nicht aus Erinnerung behaupten.

## Automatischer SYSTEM-GATE
SYSTEM-GATE wird ausgelöst bei:
- wiederholtem Fehler nach vermeintlichem Fix
- mehreren erfolglosen Fix-Versuchen
- widersprüchlichen PASS-/FAIL-Berichten
- parallelen Branches/Worktrees mit unklarem Eigentümer
- Abweichung zwischen GitHub, lokalem Code und Deployment
- wachsender Zahl von Prompts/Regeln für dasselbe Problem
- Regressionen bereits abgenommener Funktionen
- Scope-Wachstum während Reparatur
- fehlender Rückführbarkeit eines Deployments auf Commit/Digest
- Aussagen wie „das hatten wir doch schon“ oder „warum ist das wieder kaputt?“

## Verhalten nach SYSTEM-GATE
Keine weitere lokale Reparatur. Stattdessen:
1. aktuelle Wahrheit feststellen
2. Ursache statt Symptom bestimmen
3. unnötige Komplexität entfernen
4. kleinsten stabilen Benutzerweg bestimmen
5. `core/CHAOS-RECOVERY.md` anwenden, um ROLLBACK / RESTORE / PROMOTE / REPLACE / CONSOLIDATE / REWRITE zu entscheiden
6. erst danach einen neuen Implementierungsauftrag erstellen

## Rollen
- GitHub/Repo = technische Wahrheit
- laufende App = Produktrealität
- CI = technischer Prüfer
- Commit-SHA + Image-Digest = Produktionswahrheit
- ChatGPT = Systemdenken, Produktentscheidung, Diagnose, Review
- Cursor = eng begrenzte Implementierung

## Grundregel
Wenn die Wahl besteht zwischen „den aktuellen Auftrag besser lösen“ und „prüfen, ob der aktuelle Auftrag überhaupt noch der richtige Auftrag ist“, wird zuerst die zweite Frage beantwortet.

