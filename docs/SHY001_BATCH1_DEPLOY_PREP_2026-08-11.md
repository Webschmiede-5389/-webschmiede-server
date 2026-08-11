# SHY001 Batch-1 Controlled Deploy Preparation

**Datum:** 2026-08-11  
**Worktree:** `webschmiede-server-shy001-baseline-2026-08-11`  
**Branch:** `shy001-prod-baseline-2026-08-11`  
**Commits:** `7378036` (Prod Baseline) → `54e7c84` (Batch-1)  

**Nicht ausgeführt:** Deploy, Prod-DB, Service-Restart, `online_ordering`, Stripe, Google.

```
Scope: KUNDE SHY001 (+ SHARED_INFRA snack-api nur als Zielpfad dokumentiert)
```

---

## 1. Original Workspace Index Check (read-only)

**Pfad:** `…/projects/webschmiede-server`  
**Branch:** `feature/platform-unification-branding-pilot` @ `1954c72`

### Was passiert war

Vor dem Clean-Worktree waren ca. **1123 Dateien staged** (vermutlich `git add`-Rest).  
Gegenmaßnahme: **`git reset HEAD`** (mixed) – **nur Index**, Working-Tree-Inhalte nicht verworfen.

### Aktueller Befund (2026-08-11, read-only)

| Metrik | Wert |
|--------|------|
| Staged | **0** |
| Porcelain gesamt | **506** |
| Modified tracked (ca.) | **103** |
| Untracked | **1018** |
| HEAD | `1954c72` (unverändert) |

### Kritische Dateien vorhanden?

Alle geprüft und **vorhanden** (inkl. Batch-1-Hashes und Prod-Snapshot):

- `app/backend/main.py`, `order_portal.py`, `order_priority.py`, `push_notifications.py`
- `shop_mail.py`, `shop_status.py`
- `app/static/admin.html`, `order.html`
- `tests/test_order_acceptance.py`
- `_tmp_prod_snap_2026-08-11/main.py`, `admin.html`

### Interpretation

| Frage | Antwort |
|-------|---------|
| Working-Tree-Dateien weiterhin vorhanden? | **Ja** (kritische Stichprobe + Counts konsistent mit Vor-Reset-Lage ~506 porcelain) |
| Was hat sich am Index geändert? | Staging geleert (`git reset HEAD`). Kein Checkout/Discard der Inhalte |
| Dateiverlust erkennbar? | **Nein** in der Stichprobe |
| Staged-only Inhalte verloren? | **Unwahrscheinlich / kein Hinweis.** `git reset` mixed lässt Working Tree; zuvor untracked+staged Dateien sind wieder untracked. Es gab keine Hinweise auf „nur im Index, nie auf Disk“-Blobs |

**Urteil Index-Check:** Dateien intakt · Änderung war **index-only**.

---

## 2. Deploy Manifest (minimal, nur Batch-1)

Zielhost: `167.233.150.230`  
Backend: `/root/app/backend/`  
Static Spiegel: `/root/app/static/`  
Webroot: `/var/www/snackhouse-mechernich/`

| Lokaler Pfad (Worktree) | Produktiver Zielpfad | Prod-Hash vorher | Neuer Hash | Zweck | Deploy? |
|-------------------------|----------------------|------------------|------------|-------|---------|
| `app/backend/main.py` | `/root/app/backend/main.py` | `f5898fbf…b30cb0` | `27bd9590…4bc4f6ae` | Pending-Mail, Transitions, Annahme-Notify | **YES** |
| `app/backend/order_portal.py` | `/root/app/backend/order_portal.py` | `b60143d5…d4ad55` | `013335e9…3c8644` | `ALLOWED_TRANSITIONS`, SMS-Helfer | **YES** |
| `app/backend/order_priority.py` | `/root/app/backend/order_priority.py` | `a5678280…ab42ce` | `9ccb263b…04c165` | `angenommen` in ACTIVE | **YES** |
| `app/backend/push_notifications.py` | `/root/app/backend/push_notifications.py` | `89777baf…73cd6` | `dc310be4…25a451` | Pending-/Annahme-Push | **YES** |
| `app/static/admin.html` | `/root/app/static/admin.html` **und** `/var/www/snackhouse-mechernich/admin.html` | `819410e4…33a21` | `12247118…c271a` | Annehmen→angenommen, Zubereitung-Button | **YES** (beide Pfade) |
| `app/backend/shop_mail.py` | `/root/app/backend/shop_mail.py` | `2d886575…daaf8` | identisch | Status-URL schon live | **NO** |
| `app/backend/shop_status.py` | `/root/app/backend/shop_status.py` | `682949a5…dbe40` | identisch | Soft-Launch SoT | **NO** |
| `app/static/order.html` | static + Webroot | `58827c33…157fd` | identisch | Gast-UI | **NO** |
| `tests/…`, `docs/…` | — | — | — | lokal | **NO** |

**Kein** `deploy.py`-Voll-Lauf. **Kein** Repo-Sync.

**Manifest-Status:** READY (5 Dateien / 6 Upload-Ziele inkl. doppeltes `admin.html`).

---

## 3. Database Compatibility

### Schema

```sql
status TEXT DEFAULT 'neu'
```

Kein `CHECK`-Constraint, keine ENUM-Tabelle, kein FK auf Statuswerte.

### Migration nötig?

**NEIN.** `angenommen` ist ein weiterer String-Wert in derselben Spalte.

### Bestehende Orders

- Alte Status (`neu`, `zubereitung`, `fertig`, `storniert`, …) bleiben gültig.
- Live-Stichprobe (früher): `SH-1008-1433-UYZ` = `fertig` – unberührt durch Code-Deploy ohne DB-Write.
- Queries filtern typisch `status != 'storniert'` oder listen alle – **kein** Hard-Fail bei unbekanntem Wert.
- Sortierung (`order_priority`): `angenommen` neu in `_ACTIVE_STATUSES` – fertige Orders weiter in DONE.
- Analytics/Alerts: Resolve `unconfirmed_order` jetzt auch bei `angenommen` (zusätzlich zu `zubereitung`) – verbessert, bricht alte Rows nicht.
- Autoprint: druckt nur `status == "neu"` → Bondruck bei Create **unverändert**.
- Öffentliche Statusseite: Prod-`order_portal` kannte `angenommen` bereits in `STATUS_FLOW`; Batch-1 ergänzt Transitions.

**Risiko für bestehende Rows:** niedrig.

---

## 4. Backup Plan (noch nicht ausführen)

Timestamp-Platzhalter: `TS=YYYYMMDD-HHMMSS` (Server-Zeit).

### A. Produktive Dateien

```
/root/backups/shy001-batch1-$TS/
  main.py
  order_portal.py
  order_priority.py
  push_notifications.py
  admin.html                  # aus /root/app/static/
  admin.html.webroot          # Kopie aus /var/www/snackhouse-mechernich/admin.html
```

### B. DB

```
/root/backups/shy001-batch1-$TS/orders.db
# Quelle: /root/app/backend/orders.db  (cp -a, Service weiterlaufend ok für SQLite-Kopie)
```

Batch-1 ändert Schema nicht – DB-Backup trotzdem Pflicht (Betriebsregel).

### C. Config

```
/root/backups/shy001-batch1-$TS/SHY001_snackhouse.json
# Quelle: /root/app/kunden/SHY001_snackhouse.json
# Optional: /root/app/backend/.env  (nur wenn Ops-Policy erlaubt; Secrets nicht committen)
```

### D. Service-Zustand

```
systemctl is-active snack-api
systemctl status snack-api --no-pager
curl -sS http://127.0.0.1:8000/api/health
curl -sS http://127.0.0.1:8000/api/shop-status   # expect accept_orders=false
sha256sum der 5 Prod-Dateien vor Überschreiben → sha256sums-pre.txt
```

---

## 5. Rollback Plan

Wenn Smoke fehlschlägt:

1. **Dateien zurück:** Inhalt von `/root/backups/shy001-batch1-$TS/` nach  
   `/root/app/backend/{main,order_portal,order_priority,push_notifications}.py`  
   `/root/app/static/admin.html`  
   `/var/www/snackhouse-mechernich/admin.html` (aus `admin.html.webroot`)
2. **DB-Rollback:** **nicht nötig** für reinen Code-Fail (keine Migration). Nur wenn während Smoke manuell Testdaten stören → optional Orders-Backup; Schema unverändert.
3. **Service:** `systemctl restart snack-api` (nur im Rollback/Deploy-Fenster, nicht jetzt).
4. **Prüfen:**  
   - `systemctl is-active snack-api` → active  
   - `/api/health` OK  
   - SHA256 der 5 Dateien = Backup-`sha256sums-pre.txt`  
   - Admin „Annehmen“ setzt wieder `zubereitung` (altes Verhalten)  
   - Soft-Launch: `accept_orders=false` bleibt

Zielzeit: **wenige Minuten** (5 File-Copies + Restart + Health).

---

## 6. Pre-Deploy Tests (lokal, Worktree)

```
cd webschmiede-server-shy001-baseline-2026-08-11
python -m pytest tests/test_order_acceptance.py -v
→ 14 passed, 0 failed
```

`scripts/test_order_portal.py` existiert in diesem Clean-Worktree **nicht** (nur Dirty-Tree) – nicht mitgemischt.

**Unrelated (nicht in diesem Branch):** phase_a KPI Fixture-Fails (3) – separat, nicht Batch-1.

---

## 7. Post-Deploy Smoke Test Plan

Voraussetzung: Soft-Launch bleibt zu **oder** bewusst eine interne Testorder (Owner-Kanal). Keine Kunden-Öffnung in diesem Prep.

| # | Schritt | Erwartung |
|---|---------|-----------|
| SMOKE 1 | Testbestellung create (Admin/API/Owner) | Status **`neu`** |
| SMOKE 2 | Kunden-Mail/SMS/Push nach Create | Nur Pending: eingegangen / wird geprüft / wartet auf Annahme – **kein** „angenommen“ / kein grünes ✓-Fertiggefühl |
| SMOKE 3 | Admin öffnen | Bestellung als **`neu`** sichtbar |
| SMOKE 4 | Admin **ANNEHMEN** | Status **`angenommen`** |
| SMOKE 5 | Kunde Annahme-Kanal | **Genau eine** Annahme-Nachricht (`order_accepted`); Zweitklick Annehmen → keine zweite |
| SMOKE 6 | Admin **ZUBEREITUNG** | Status **`zubereitung`** |
| SMOKE 7 | Kunde | Zubereitungs-Status/Notify wie bisher |
| SMOKE 8 | Neue Bestellung → Ablehnen/Storno aus `neu` | → **`storniert`** OK |
| SMOKE 9 | Autoprint / Bondruck | Neuer `neu`-Auftrag wird gedruckt (Agent pollt `status==neu`) |
| SMOKE 10 | Bestehende `fertig`-Orders | unverändert in DB/Admin |

Zusätzlich API-Negativ: `POST …/status` mit `neu→zubereitung` → **400**.

---

## 8. Pilot / Online Ordering (nur Doku)

### Aktuell (Live-Evidence 2026-08-11)

| Schalter | Wert |
|----------|------|
| `location.fulfillment.online_ordering` (kunden JSON) | **false** |
| `/api/shop-status` → `accept_orders` | **false** |
| Reasons | `online_ordering_disabled` |
| `settings.online` | `"1"` (kein Manual-Offline) |
| `paused` | false |

### Unterschied

| Schalter | Bedeutung |
|----------|-----------|
| **`online_ordering`** (kunden.json) | Produkt-/Tenant-Schalter: Online-Kanal grundsätzlich erlaubt? |
| **`settings.online`** | Manuelle Pause: `0` = Online pausiert (Ampel/Accept über SoT) |
| **`accept_orders`** | **Abgeleiteter** Live-Status aus SoT (nicht direkt „umlegen“) |

### Für Donnerstag (wenn Freigabe)

1. `online_ordering: true` in `SHY001_snackhouse.json` + Deploy/Reload Config  
2. Sicherstellen `settings.online=1` und keine `pause_until`-Sperre  
3. Homepage-CTAs von Telefon zurück auf Bestellen  
4. Dann erst Smoke mit echter Gast-Bestellung  

**Beide erforderlich?** Für Gast-Bestellen: **`online_ordering=true`** ist der harte Blocker jetzt. `settings.online=1` ist schon gesetzt. `accept_orders` folgt automatisch, wenn Laden offen + SoT grün.

**Begrenzter Pilot?** Ja: Soft-Launch offen nur in Öffnungsfenster; oder weiter `online_ordering=false` und nur interne Testorders über Owner/API – Batch-1-Code kann **vorher** deployt werden, ohne Online zu öffnen.

**Noch nicht aktivieren.**

---

## 9. Deploy Command Plan (NICHT AUSFÜHREN)

### Prinzip

- Nur Manifest-YES-Dateien  
- Vorher Backup §4  
- **Kein** `python deploy.py` (würde Dirty/fremde Dateien riskieren)  
- Quelle: **dieser Worktree** @ `54e7c84`

### Schritte (später, nach Freigabe)

1. `TS=$(date +%Y%m%d-%H%M%S)` auf Server; Backup-Dir anlegen; Dateien+DB+JSON+sha256sums-pre kopieren.  
2. Lokal (Worktree) SHA256 der 5 Dateien notieren.  
3. SFTP/scp **nur**:
   - `main.py` → `/root/app/backend/main.py`
   - `order_portal.py` → `/root/app/backend/order_portal.py`
   - `order_priority.py` → `/root/app/backend/order_priority.py`
   - `push_notifications.py` → `/root/app/backend/push_notifications.py`
   - `admin.html` → `/root/app/static/admin.html`
   - `admin.html` → `/var/www/snackhouse-mechernich/admin.html`
4. `systemctl restart snack-api`  
5. Health + SHA256-Verify post  
6. Smoke §7  
7. Bei Fail → Rollback §5  

Optional: kleines dediziertes Script `scripts/deploy_shy001_batch1.py` **erst bei Freigabe** schreiben/ausführen – nicht Teil dieses Preps.

---

## 10. BATCH 1 DEPLOY PREP

| Check | Urteil |
|-------|--------|
| Original dirty workspace files intact | **YES** |
| Index-only change from git reset | **YES** |
| Minimal deploy manifest | **READY** |
| DB migration required | **NO** |
| Rollback plan | **READY** |
| Local tests | **14 passed / 0 failed** |
| Post-deploy smoke plan | **READY** |
| Pilot switches identified | **YES** |
| Controlled Batch-1 deployment recommendation | **GO** |

**GO-Bedeutung:** Prep ist deploy-fähig. Ausführung erst nach ausdrücklicher Freigabe. Soft-Launch/`online_ordering` bleibt aus, bis separat freigegeben.

**STOPP. Nicht deployen.**
