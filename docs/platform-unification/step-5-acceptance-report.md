# Step 5 — Branding Pilot Abschlussbericht

**Datum:** 2026-08-04 (UTC+2)  
**Scope:** AGENCY / SHARED_INFRA  
**Production-Deploy:** nein

---

## Finales Urteil

# BRANDING_PILOT_READY

---

## Commits / Branches

| Repo | Branch | Commit |
|------|--------|--------|
| webschmiede-server | `feature/platform-unification-branding-pilot` | `b8e2bf2` (Evidence/Scripts), Memory `053f62d` |
| CRM (Abnahme) | `feature/platform-unification-branding-pilot-step5` (Worktree) | `4af56fc` (basiert auf `878cc23`) |
| CRM (Arbeitskopie) | `feature/platform-unification-branding-pilot` @ `c452390` + Dialer-WIP | **nicht verändert** |

**Stash:** `wip-before-branding-pilot-step3` unverändert belassen (nicht apply/drop).

---

## Getestete Umgebung

| Größe | Wert |
|-------|------|
| CRM URL | `http://127.0.0.1:8093` |
| App | WebSchmiede CRM BRANDING-PILOT |
| APP_ENV | staging |
| Datenbank | **PostgreSQL 16.14** (`postgresql-crm-parity-16`, Port `127.0.0.1:55432`) |
| DB-Name | `crm_branding_pilot` (eigene DB, keine Production, keine Remote-Container) |
| Treiber | `postgresql+psycopg://…` |
| Outbound / n8n / SMTP | deaktiviert |
| Seed | Admin `branding-pilot@example.local`, Firma `BRANDING PILOT TESTDATA` |
| Worktree | `projects/crm-branding-pilot-wt` @ `878cc23` (Dialer-WIP der Hauptkopie isoliert) |

**Reproduktion:**

```text
python scripts/branding_pilot_staging.py bootstrap   # ensure-db → migrate → seed → start → health
python scripts/branding_pilot_browser_drill.py
python scripts/branding_pilot_agency_tools_e2e.py
python scripts/branding_pilot_staging.py stop
```

Env: `CRM_ROOT` → Worktree, `CRM_VENV` → `projects/crm/.venv/Scripts/python.exe`

---

## Migrationen

- Alembic `upgrade head` auf frischer DB `crm_branding_pilot`
- Revision: **`017_sales_os_mvp`**
- Ergebnis: **ok** (001 → 017)

---

## Browser-Drill

Evidence: `docs/platform-unification/evidence/step-5/browser-drill.json`

| Check | Ergebnis |
|-------|----------|
| Login lädt / funktioniert | pass |
| App-Shell / Sidebar / Mandant | pass |
| Mobile Nav 390/768 | pass (`aria-expanded` open/close) |
| CRM Kernseiten (/, companies, pipeline, tasks, settings) | pass |
| Formulare/Buttons | pass |
| Console kritische Errors | **0** |
| Kern-Request-Fails | **0** |
| CSRF-Login (Token im Form) | pass |
| Logout | pass |
| Gesamtergebnis | **pass: true** |

---

## Viewports 390 / 768 / 1440

Screenshots: `docs/platform-unification/evidence/step-5/screenshots/`

| Viewport | Login | Shell | Liste | Detail/Form | Mobile Nav | Urteil |
|----------|-------|-------|-------|-------------|------------|--------|
| 390 | ok | ok | ok (Table-Wrap) | ok | ok | pass |
| 768 | ok | ok | ok | ok | ok | pass |
| 1440 | ok | ok | ok | ok | n/a | pass |

Visuell geprüft (Screenshots): Orange `#FF6600`, Logo BrandLockup, STAGING-Badge, kein Gold `#C9A84C` auf Login/Shell, kein Leads-Orange-Rest in den Baselines.

**Minimal-Fix:** Unternehmen-Liste → `.table-wrap { overflow-x: auto }` (kein Seiten-Horizontalscroll bei 390). Kein Redesign.

---

## Agency-Werkzeuge E2E

Evidence: `docs/platform-unification/evidence/step-5/agency-tools-e2e.json`

| Check | Ergebnis |
|-------|----------|
| Isolierter Mini-Flask Port 18099 | ok (kein Production-Container) |
| `GET /api/agency/tools` auth | 12 Einträge, `ok: true` |
| Ohne Creds | **401** |
| Browser 390/1440 Karten | **pass** |
| Screenshots | `agency-tools-390.png`, `agency-tools-1440.png`, `agency-shell-1440.png` |

Hinweis: Volles `agency.html`-Auth-JS braucht `/agency-auth.js` (404 im Stub). API + Werkzeuge-UI-Pilotseite decken Registry/Auth/Render ab; Production-Agency unverändert.

---

## Accessibility / Performance

| Thema | Ergebnis |
|-------|----------|
| Labels Login | `login-email` / `login-password` vorhanden |
| Skip-Link | vorhanden |
| Nav-Toggle | `aria-controls`, `aria-expanded` |
| Fokus | Tab erreicht interaktive Elemente (Sample im Drill) |
| Kritische a11y-Verstöße | keine im Drill erkannt |
| Kontrast | Orange auf Weiß / dunkle Schrift auf Hell — lesbar in Screenshots |
| Login-Zeit | ~0,9–1,2 s (lokal, headless) |
| Performance-Projekt | nicht beauftragt; keine kritische Verschlechterung beobachtet |

---

## CRM Full-Suite — 136 vs 246 (verbindliche Erklärung)

| Lauf | Runner-Root | Documented Commit | Ergebnis |
|------|-------------|-------------------|----------|
| Step 4 | `projects/crm` (Hauptordner) | `3276689` (Evidence-Header) | **246 passed** |
| Step 5 | `projects/crm-branding-pilot-wt` (isolierter Worktree) | `878cc23` + `4af56fc` | **136 collected, 136 passed, 0 failed** |

**Ursache der Differenz (kein Test-Ausschluss):**

1. **Kein pytest-Deselect / keine Marker-Filter** in Step 5 — `pytest tests/ -q` ohne `-k` / `-m`.
2. **Anderer Dateibestand im Runner-Root:** Step 4 lief im CRM-Hauptordner; die Evidence nennt Commit `3276689`, sammelte dort aber **246** Tests (Working-Tree-Inhalt zum Laufzeitpunkt, nicht identisch mit einem reinen Worktree-Checkout).
3. **Step 5 absichtlich kleiner/sauber:** nur committed Tests auf dem Pilot-Stand `878cc23` im Worktree — **ohne** Dialer-/fremde WIP-Testdateien aus dem Hauptordner.
4. Damit ist 136 = vollständige Suite des **abgenommenen Commit-Stands**, nicht eine gekürzte Teilmenge derselben 246.

Evidence: `evidence/step-4/full-suite-after-fix.txt` (Zeile `commit=3276689`, `246 passed`) · `evidence/step-5/full-suite-after-step5.txt` (`136 passed`).

---

## Geänderte / neue Dateien (dieser Schritt)

### webschmiede-server
- `scripts/branding_pilot_staging.py`
- `scripts/branding_pilot_browser_drill.py`
- `scripts/branding_pilot_agency_tools_e2e.py`
- `docs/platform-unification/step-5-acceptance-report.md` (diese Datei)
- `docs/platform-unification/evidence/step-5/**`

### CRM Worktree (`crm-branding-pilot-wt`)
- `app/templates/companies/list.html` (table-wrap)
- `app/static/css/crm.css` (`.table-wrap`)
- `.env.branding-pilot.example`
- `.gitignore` (`.env.branding-pilot`, staging branding-pilot Pfade)
- `.env.branding-pilot` lokal, **nicht** committen

---

## Offene Risiken

1. CRM-Hauptordner hat Dialer-WIP inkl. `base.html` — Abnahme lief bewusst auf Worktree `878cc23`, nicht auf schmutziger Hauptkopie.
2. Agency-E2E nutzt isolierten Stub (Port 18099), nicht Live-`digitalehandwerkskunst.de/agency`.
3. Docker Desktop lokal fehlt; Nachweis über Windows-Postgres-Parity-Service (Production-äquivalente Engine).
4. Table-Wrap bisher nur Unternehmen-Liste; andere breite Tabellen können auf 390 noch lokal scrollen müssen.

---

## Rollback

```text
# CRM Staging stoppen
python scripts/branding_pilot_staging.py stop

# DB verwerfen (nur Pilot-DB)
psql -h 127.0.0.1 -p 55432 -U postgres -c "DROP DATABASE IF EXISTS crm_branding_pilot;"

# Worktree entfernen
git -C projects/crm worktree remove projects/crm-branding-pilot-wt --force

# Server: Squash-Commit auf Pilot-Branch zurücknehmen
git -C projects/webschmiede-server checkout feature/platform-unification-branding-pilot
git -C projects/webschmiede-server reset --hard ff4fa6f

# CRM: Merge-Commit zurücknehmen
git -C projects/crm checkout feature/platform-unification-branding-pilot
git -C projects/crm reset --hard 4e6f9dc

# Production: keine Änderung vorgenommen
```

---

## Abschluss Merge (2026-08-04) — `MERGED_NO_DEPLOY`

| Größe | Wert |
|-------|------|
| Zielbranch (beide Repos) | `feature/platform-unification-branding-pilot` |
| Server Squash | `44881c2` ← Soft-Reset von `b8e2bf2…4aff199` auf Basis `ff4fa6f` |
| CRM Merge | `81398b4` ← `feature/platform-unification-branding-pilot-step5` (`4af56fc`) in Pilot-Branch |
| CRM vor Merge | `4e6f9dc` |
| Staging Port 8093 | **down** |
| Postgres-Parity-Service | läuft weiter (shared lokal, kein Prod; nur App gestoppt) |
| Server-Stash | `wip-before-branding-pilot-step3` **unverändert** |
| Dialer-/fremde WIP | Working-Tree CRM weiter dirty/untracked (**nicht** gestaged) |
| Production-Deploy | **nein** |
| Post-Merge Tests | fokussiert **10 passed** (`test_014_*`, `test_handwerk_inquiry_template`); Full-Suite-Lauf (295 collected) bei ~48 % gehängt → abgebrochen (kein Merge-Scope-Fail nachweisbar) |
| Alembic Head (CRM Branch) | `021_dialer_call_control_terminal` (Branch enthält Dialer; Pilot-Abnahme war `017` auf Worktree) |
| Browser-Drill erneut | nicht nötig (Merge konfliktfrei, Scope nur table-wrap/CSS/env/gitignore/docs) |

**Urteil: MERGED_NO_DEPLOY**
