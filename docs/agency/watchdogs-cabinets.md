# Watchdogs & Schränke (beide Server)

Stand: 2026-07-17

## Idee

Prüfen → begrenzt reparieren → dich mailen. **Nicht** den Server totlaufen.

## Takt

**10–15 Minuten** (nicht Sekunden). Server-Power erst später erhöhen, wenn nötig.

## Schränke (`watchdog_cabinets.py`)

| Schrank | Default |
|---------|---------|
| `flock` | kein Parallel-Lauf derselben Prüfung |
| Alert-Cooldown | 4 Stunden pro Fehler-Fingerprint |
| Repair-Budget | max. 2× / Stunde (DNS, snack-api Restart) |

## Was läuft wo

| Job | web-01neu | auto-01neu |
|-----|-----------|------------|
| Resource (RAM/Disk/Load) | */15 | */15 |
| Route/DNS | :10/:25/:40/:55 | */15 |
| Kunden-Portale | :05/:20/:35/:50 | :08/:23/:38/:53 |
| Nightly + Stefan | – | wie bisher |

## Install

```bash
python scripts/setup_dual_watchdogs.py
```

## Logs

- `/var/log/resource-watchdog.log`
- `/var/log/route-watchdog.log`
- `/var/log/customer-portal-watchdog.log`
- State: `/var/lib/webschmiede/cabinets/`
