# Discovery + ETA + Hirn-Wächter + Night-Worker

Stand: 2026-07-20

## 1 GitHub-Token

`GITHUB_TOKEN` in `cursor.secrets.local` – aktuell noch **leer** (lokal + Server).
Ohne Token: Cursor ja, Auto-Deploy nein.

## 2 Discovery

Bau-Auftrag → Rückfragen + Vorschläge → „mach das“ / „ja“.
Überspringen: „ohne fragen“ / „direkt bau“.

## 3 ETA + Job-Watchdog

Keine Fake-Minuten. Jobs in `nils-jobs.json`, Overdue-Ping.
Limit: `NILS_JOB_MAX_MINUTES` (default 25).

## 4 Hirn-Wächter / Night-Worker

Alle 20 Min: API, Telegram-Webhook, stuck Locks, overdue Jobs, soft-repair.
Nacht 20:00 UTC Digest. Telegram: `hirnwächter`.

## 5 GitHub-Stand

Vor Cursor-Aufträgen: lokalen Stand pushen. Night-Worker meldet fehlenden Token.
