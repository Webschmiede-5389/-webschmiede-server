# SHY001 Clean Prod-Baseline Branch + Batch-1 Port

**Datum:** 2026-08-11  
**Strategie:** Option C  
**Kein Deploy · Keine Prod-DB · Kein Stripe**

---

## Phase 1 – Sicherheit / Plan

| Feld | Wert |
|------|------|
| Original-Workspace | `…/projects/webschmiede-server` |
| Original-Branch | `feature/platform-unification-branding-pilot` |
| HEAD (Start) | `1954c72` |
| Dirty-Tree | ~506 porcelain / ~1000 untracked – **unangetastet** (Inhalte) |
| Clean Worktree | `…/projects/webschmiede-server-shy001-baseline-2026-08-11` |
| Clean Branch | `shy001-prod-baseline-2026-08-11` |
| Baseline-Quelle | Read-only Prod-Snapshot `_tmp_prod_snap_2026-08-11/` (+ hash-gleiche Cores) |

**Zwischenfall (behoben):** Kurzzeitig waren im Original-Workspace Dateien gestaged (`git add`-Rest). Mit `git reset HEAD` (nur Index) wieder unstaged. Dirty-Inhalte erhalten. Porcelain wieder ~506.

**Hinweis:** Ein älterer Worktree-Pfad `…-shy001-prod-baseline-…` ließ sich wegen Permission nicht löschen; neuer sauberer Worktree liegt unter `…-shy001-baseline-2026-08-11`.

Dirty Tree diente **nur lesend** als Quelle der bereits geprüften Batch-1-Hashes.

---

## Phase 2–3 – Prod Baseline

Commit: `7378036` – `chore(shy001): pin prod baseline cores from 2026-08-11 snapshot`

| Datei | Prod-SHA256 | Match |
|-------|-------------|-------|
| `app/backend/main.py` | `f5898fbfd573…b30cb0` | YES |
| `app/backend/order_portal.py` | `b60143d57551…d4ad55` | YES |
| `app/backend/order_priority.py` | `a5678280ad4a…ab42ce` | YES |
| `app/backend/push_notifications.py` | `89777bafa9bc…73cd6` | YES (entsprach bereits HEAD) |
| `app/backend/shop_mail.py` | `2d886575ab20…daaf8` | YES |
| `app/backend/shop_status.py` | `682949a5b570…dbe40` | YES |
| `app/static/admin.html` | `819410e45c41…33a21` | YES |
| `app/static/order.html` | `58827c33e667…157fd` | YES |

**PROD BASELINE MATCH = HIGH CONFIDENCE**

Neu getrackt: `order_portal.py`, `order_priority.py`, `shop_mail.py`, `shop_status.py`.

---

## Phase 4–5 – Batch-1 Port (nur geprüfte Deltas)

Quelle: Dirty-Tree-Dateien mit **exakt** den gegen Prod verifizierten Batch-1-Hashes.

| Datei | Batch-1-SHA256 | Diff vs Baseline |
|-------|----------------|------------------|
| `main.py` | `27bd9590…4bc4f6ae` | P0-02/03/04 + `import shop_mail` |
| `order_portal.py` | `013335e9…3c8644` | Transitions + SMS-Helfer |
| `order_priority.py` | `9ccb263b…04c165` | `angenommen` in ACTIVE |
| `push_notifications.py` | `dc310be4…25a451` | Pending-Body + Push angenommen |
| `admin.html` | `12247118…c271a` | Minimal: Labels/Buttons/Filter/CSS/Ops |

**Nicht übernommen:** KPI, Analytics, WLAN/Drucker-Experimente, Stripe, Follow-ups, Agency-Web, sonstiger Dirty Tree.

### Admin Minimal Patch (gegen Prod-Baseline)

- `neu` → Button Annehmen → `angenommen`
- `angenommen` → Button Zubereitung → `zubereitung`
- Status-Label + minimale CSS (`.sl-angenommen`, Kartenkante, Ops-Border)
- Filter-Pill „Angenommen“
- `OPS_STATUS_PRIMARY` angepasst
- Landscape Intake-Spalte neu+angenommen

Stat: `admin.html` | 29 insertions / wenige Deletions – kein Mega-UI-Import.

---

## Phase 6 – Tests

```
pytest tests/test_order_acceptance.py -v
→ 14 passed in 0.12s
```

Abgedeckt: CREATE/`neu`-Semantik, `neu→angenommen`, `neu→zubereitung` verboten, `angenommen→zubereitung`, Idempotenz, spätere Flows, Pending-SMS, Accepted-SMS, message_log-Idempotenz-Marker.

**phase_a KPI (3 Fixture-Fails):** bewusst **nicht** in diesen Branch übernommen / nicht mit Batch-1 vermischt.

---

## Phase 7 – Source Hygiene (Dateiliste Branch)

### Commit 1 – Prod Baseline
- `app/backend/main.py` (Prod)
- `app/backend/order_portal.py` (neu tracked, Prod)
- `app/backend/order_priority.py` (neu tracked, Prod)
- `app/backend/shop_mail.py` (neu tracked, Prod)
- `app/backend/shop_status.py` (neu tracked, Prod)
- `app/static/admin.html` (Prod)
- `app/static/order.html` (Prod)

### Commit 2 – Batch-1 (+ Tests + Doc)
- `app/backend/main.py`
- `app/backend/order_portal.py`
- `app/backend/order_priority.py`
- `app/backend/push_notifications.py`
- `app/static/admin.html`
- `tests/test_order_acceptance.py`
- `docs/SHY001_CLEAN_BASELINE_BATCH1_2026-08-11.md`

**Unexpected diffs:** NONE (innerhalb dieses Scope)

---

## Phase 8 – Nicht gemacht

- Production-Deploy  
- `online_ordering` aktivieren  
- Stripe  
- Prod-DB / Service-Restart  

---

## SHY001 CLEAN BASELINE RESULT

| Check | Urteil |
|-------|--------|
| Dirty original workspace untouched | **YES** (Inhalte; Index-Reset war notwendig) |
| Clean branch/worktree created | **YES** |
| Prod baseline confidence | **HIGH** |
| Core modules tracked | **YES** |
| Batch-1 isolated | **YES** |
| admin.html minimal patch only | **YES** |
| Acceptance tests | **14 passed / 0 failed** |
| Unexpected diffs | **NONE** |
| Ready for controlled Batch-1 deploy preparation | **YES** |
| Ready for Stripe development on this branch | **YES** (Planung/Impl. erst nach Freigabe; nicht in diesem Schritt) |

### Pfade

- Worktree: `C:/Users/kumex/OneDrive/Desktop/Jarvis/My_Company_Hub/projects/webschmiede-server-shy001-baseline-2026-08-11`
- Branch: `shy001-prod-baseline-2026-08-11`
- Original Dirty: `…/webschmiede-server` @ `feature/platform-unification-branding-pilot`

**STOPP.** Kein Deploy. Keine Stripe-Implementierung.
