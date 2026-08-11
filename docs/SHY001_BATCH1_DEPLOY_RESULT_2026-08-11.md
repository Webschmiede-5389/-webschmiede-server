# SHY001 Batch-1 Controlled Deploy Result

**Datum:** 2026-08-11  
**Worktree:** `webschmiede-server-shy001-baseline-2026-08-11`  
**Branch:** `shy001-prod-baseline-2026-08-11` @ `54e7c84` (+ Prep-Doc)  
**Host:** `167.233.150.230` · Service `snack-api`

```
Scope: KUNDE SHY001
online_ordering: unverändert false
accept_orders: unverändert false
```

---

## 1. Pre-Deploy Safety

| Check | Ergebnis |
|-------|----------|
| Server | `167.233.150.230` (web-01) |
| Service vor Deploy | `active` / `running` |
| Pre-Hashes (5 Dateien) | **OK** (entsprechen dokumentierter Prod-Baseline) |
| Backup | **YES** |

**Backup-Pfad:** `/root/backups/shy001-batch1-20260811-143859/`  

Inhalt: `main.py`, `order_portal.py`, `order_priority.py`, `push_notifications.py`, `admin.html`, `admin.html.webroot`, `orders.db`, `SHY001_snackhouse.json`, `sha256sums-pre.txt`

---

## 2. Minimal Deploy

Nur diese Uploads:

| Datei | Ziel | Post-SHA256 |
|-------|------|-------------|
| `main.py` | `/root/app/backend/main.py` | `27bd9590…4bc4f6ae` |
| `order_portal.py` | `/root/app/backend/order_portal.py` | `013335e9…3c8644` |
| `order_priority.py` | `/root/app/backend/order_priority.py` | `9ccb263b…04c165` |
| `push_notifications.py` | `/root/app/backend/push_notifications.py` | `dc310be4…25a451` |
| `admin.html` | `/root/app/static/admin.html` + Webroot | `12247118…c271a` |

**Files deployed: 5 / 5** (admin doppelt auf Spiegel + Webroot).  
Kein Full-Repo-Deploy. Kein Stripe/Google/Online-Schalter.

---

## 3. Service Reload

- `systemctl restart snack-api`
- Danach: **active**
- Journal: sauberer Stop/Start, Worker booten (keine Import-Crash-Traces in Tail)

---

## 4. Technical Health

| Check | Ergebnis |
|-------|----------|
| `/api/health` | 200 `status=ok` |
| `/api/shop-status` | 200 |
| Admin-Seite | 200 |
| Bestellen-Seite | 200 |
| Soft-Launch | `accept_orders=false`, `online_ordering_enabled=false`, reason `online_ordering_disabled` |

---

## 5. Smoke Tests

Interne Methode (Soft-Launch bleibt zu): DB-Insert Testorder + Admin-**Session-Token** (`/api/admin/login`; `ADMIN_ALLOW_PASSWORD_HEADER=0`).

Erster Smoke-Lauf scheiterte an Header-Auth (401) → kein Rollback nötig (Deploy/Hashes/Health ok). Zweiter Lauf mit Session: erfolgreich.

| # | Ergebnis | Evidenz |
|---|----------|---------|
| 1 | **PASS** | Order `SH-B1S-144057` Status `neu` |
| 2 | **PASS** | Pending-SMS-Text: eingegangen + prüfen + Annahme folgt |
| 3 | **PASS** | Admin API listet Order als `neu` |
| 4 | **PASS** | `neu → angenommen` HTTP 200 |
| 5 | **PASS** | `message_log` template `order_accepted` Count 1→1 nach Zweitklick; `unchanged: true` |
| 6 | **PASS** | `angenommen → zubereitung` HTTP 200 |
| 7 | **PASS** | Zubereitung-Status ok; `neu → zubereitung` → 400 „nicht erlaubt“ |
| 8 | **PASS** | `neu → storniert` auf Zweitorder HTTP 200 |
| 9 | **NOT RUN** | Kein `autoprint.py` auf Server-Pfaden gefunden; kein Live-Druck (Ladenbetrieb). Batch-1 ändert Autoprint nicht; lokal Filter `status==neu` unverändert |
| 10 | **PASS** | `SH-1008-1433-UYZ` weiter `fertig`; fertig-Count 4 unverändert |

Admin-UI enthält `next:'angenommen'` (Webroot verifiziert).

---

## 6. Cleanup

Testorders `SH-B1S-144057` / `-B` (und zuvor `SH-BATCH1-143859*`) auf **`storniert`** + Note `BATCH1_SMOKE_*` / `BATCH1_SMOKE_CLEANUP`.  
Historische Kundenorders unangetastet.

---

## 7. Soft-Launch nach Deploy

| Schalter | Wert |
|----------|------|
| `online_ordering_enabled` | **false** |
| `accept_orders` | **false** |
| reasons | `online_ordering_disabled` |

**Nicht freigeschaltet.**

---

## 8. Rollback

**Nicht erforderlich.** Deploy-Hashes korrekt, Service healthy, Smoke (Session) PASS.

Rollback-Backup bleibt unter `/root/backups/shy001-batch1-20260811-143859/` verfügbar.

---

## BATCH 1 PROD RESULT

| Check | Urteil |
|-------|--------|
| Backup created | **YES** |
| Files deployed | **5 / 5** |
| Service healthy | **YES** |
| Smoke 1 | **PASS** |
| Smoke 2 | **PASS** |
| Smoke 3 | **PASS** |
| Smoke 4 | **PASS** |
| Smoke 5 | **PASS** |
| Smoke 6 | **PASS** |
| Smoke 7 | **PASS** |
| Smoke 8 | **PASS** |
| Smoke 9 | **NOT RUN** |
| Smoke 10 | **PASS** |
| Rollback required | **NO** |
| online_ordering still OFF | **YES** |
| accept_orders still OFF | **YES** |
| Batch 1 production status | **PASS** |
| Ready for Stripe Batch 2 development | **YES** |

**STOPP.** Kein Stripe in diesem Schritt. Soft-Launch bleibt zu bis separate Freigabe.
