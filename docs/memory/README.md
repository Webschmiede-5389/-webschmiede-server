# Agency-Gedächtnis (docs/memory)

Das ist die **Wissensbasis für Cursor-Chats**, nicht das Branchen-Pack für den Bot (`knowledge/packs/`).

Ziel: Projekte gehen weiter, Chats wechseln, der Agent vergisst weniger, weil Fakten im Repo liegen.

## Dateien

| Datei | Rolle |
|-------|--------|
| [CURRENT.md](CURRENT.md) | Was gerade läuft (1 Seite, immer aktuell) |
| [HANDOFF.md](HANDOFF.md) | Vorlage für Chat-Neustart |
| [decisions.md](decisions.md) | Beschlüsse (kurz, datiert) |
| [topics/](topics/) | Ein Thema pro Datei |

## Wer schreibt wann

- **Agent:** nach jedem Beschluss oder wenn ein neuer Chat vorgeschlagen wird
- **Du:** nur wenn du etwas korrigierst („das stimmt nicht“)

## Neuer Chat

Agent füllt `HANDOFF.md` → du öffnest neuen Chat → erste Nachricht = Inhalt von HANDOFF (oder „lies docs/memory/CURRENT.md und HANDOFF.md“).

## Nicht speichern

Secrets, Passwörter, Tokens. Nur: fehlt / gesetzt / wo konfigurieren.
