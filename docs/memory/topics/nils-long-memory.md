# Nils Langzeitgedächtnis + Multimodal

Stand: 2026-07-20

## Was live ist

1. **Jahre-Gedächtnis** (`telegram_memory.py`, Tabelle `nils_long_memory` in orders.db)
   - Fakten/Präferenzen dauerhaft
   - Abruf bei jedem Turn
   - Auto-Extrakt + Tages-Summary
   - Befehle: `merk dir: …`, `vergiss: …`, `gedächtnis`

2. **Foto/PDF in Telegram** → Vision bzw. PDF-Text → Antwort

3. **Stärkere Live-Suche** → DuckDuckGo + Wikipedia + mehr Trigger

## Backup

orders.db enthält das Gedächtnis → Agency-Backups mitnehmen.
