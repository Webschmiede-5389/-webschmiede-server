# Transportkalkulation (MbP / Tobias)

Stand: 2026-07-17

## Live

https://digitalehandwerkskunst.de/transport-kalkulator  
https://digitalehandwerkskunst.de/transport-kalkulator.html

PWA: Manifest + Service Worker (Hülle offline).

## Funktionen MVP

- Stationen (eigen/fremd), Start Krefeld editierbar
- km manuell oder grob aus OSM/OSRM (inkl. Rückfahrt)
- Kosten: Leasing, Diesel, Maut, Fahrer/Verwaltung, Standzeiten, Marge
- Alle Sätze unter **Einstellungen** speicherbar (localStorage)
- Optional Paletten-Umlage
- Text zum Kopieren, klar als Entwurf

## Dateien

- `app/static/transport-kalkulator.html`
- `app/static/transport-kalkulator.webmanifest`
- `app/static/transport-kalkulator-sw.js`
