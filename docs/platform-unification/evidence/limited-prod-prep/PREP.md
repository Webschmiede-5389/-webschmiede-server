# Limited Production Deploy Prep (Branding/UI) — READ-ONLY

**Urteil:** `READY_FOR_LIMITED_PRODUCTION_EXECUTION`  
**Deploy in diesem Schritt:** **nein**

## Freigaben

| Item | Wert |
|------|------|
| CRM Release-Commit | `68ede4d842b4fdfe67f2d61826ce70a47af25801` |
| Server Evidence Basis | `22a550a` + Folge `ad670b6`…`a7f7c36` |
| Status vorher | `READY_FOR_LIMITED_PRODUCTION_DEPLOY` |

## Release-Quelle

| Feld | Wert |
|------|------|
| Release-Checkout-Pfad | `C:\Users\kumex\OneDrive\Desktop\Jarvis\My_Company_Hub\projects\crm-release-68ede4d` |
| Art | frischer `git worktree add --detach` auf `68ede4d` |
| Commit-Match | **ja** (`68ede4d842b4fdfe67f2d61826ce70a47af25801`) |
| Working Tree clean | **ja** (0 porcelain) |
| Untracked im Release | **nein** |
| Secrets aus Git | nur `*.example` getrackt; **keine** echten `.env`/Credentials im Release-Checkout |

**Bestätigung dirty Trees nicht verwendet:**  
CRM-Main bleibt dirty (~263, ~99 Dialer) und ist **nicht** Deploy-Quelle.  
Release-Worktree ist die einzige freigegebene Quelle.

## Production-Ausgangsstand (read-only)

| Feld | Wert |
|------|------|
| Production-Ausgangscommit | **`f0f22780a9a1371ef91298024c84f1bd5aa0ffd6`** |
| Quelle | Docker Image Label `git.sha` auf `crm-app-prod:local` (`pol001.handover=clean-commit`) |
| Image-ID | `sha256:640c9e79ea55d037ab9aba191f70f92409b4ded0a01f68e9a87c0e2f3168068d` |
| Health | `https://crm.digitalehandwerkskunst.de/health` → `ok`, `env=production` |
| Services | `crm-app-prod` healthy, `crm-db-prod` healthy |
| Alembic Prod | `016_dl_meta_context` |
| Bind-Mounts App-Code | **keine** (UI liegt im Image unter `/app/app/...`) |
| Host `/opt/crm-prod` Git | **kein** `.git` |
| Backup-Pfad vorhanden | `/opt/crm-prod/backups/` (u. a. Dump `20260801T215808Z`) |

### Cache
- `/static/css/crm.css` via Nginx: `200`, `etag` gesetzt, `last-modified` 2026-08-01  
- Nach UI-Deploy: Container-Neustart / neues Image → neuer ETag erwartet

### Migration
- **Keine DB-Migration** für Limited Branding/UI  
- Release-Tree enthält später Dialer-Migrationen `017`–`021` — dürfen bei Limited Deploy **nicht** laufen

## Deploy-Diff / Scope

### Verboten: Full-Tree `f0f2278..68ede4d`
- **212 Dateien**, davon ~**70** Dialer-/Softphone-/PSTN-ähnlich  
- 16 Commits dazwischen (Dialer, Sales-OS, Softphone, …)  
- Ein `docker compose build` aus dem kompletten `68ede4d`-Tree wäre **kein** Limited Branding-Deploy

### Erlaubt: UI-only aus Release-Checkout

| Status | Pfad |
|--------|------|
| M | `app/static/css/crm.css` |
| M | `app/templates/companies/list.html` |
| M | `app/templates/companies/archived.html` |
| M | `app/templates/dashboard/index.html` |
| M | `app/templates/leads/list.html` |
| M | `app/templates/tasks/list.html` |
| A | `app/templates/vertrieb/anrufliste.html` (auf Prod-Image bisher fehlend) |

**Nicht auf Production kopieren:** `tests/test_branding_ui_layout.py` (nur Test)

Dialer / Provider / PSTN / Allowlist / Businesslogik / Migrationen: **unverändert lassen**.

## Pre-Deploy-Checks (Release-Checkout)

| Check | Ergebnis | Anzahl/Detail |
|-------|----------|---------------|
| `test_branding_ui_layout` + `test_security_gate` | bestanden | **22** |
| compileall `app` | bestanden | exit 0 |
| Import `app.main` | bestanden | Webschmiede CRM |
| Jinja parse UI-Templates | bestanden | 6 Templates |
| Statischer Scope-Check (table-wrap / Badge-CSS) | bestanden | ok |
| Secret-Scan UI-Pfade | bestanden | kein echtes Secret (False Positive: Wort „token“ in Kommentar `webschmiede-tokens.css`) |
| Dialer/PSTN Live-Call-Tests | **nicht ausgeführt** | bewusst |

## Backup-Plan (vor Execution)

1. Image einfrieren:  
   `docker tag crm-app-prod:local crm-app-prod:pre-branding-ui-68ede4d`  
   optional: `docker save crm-app-prod:pre-branding-ui-68ede4d -o /opt/crm-prod/backups/crm-app-prod-pre-branding-ui-<TS>.tar`
2. UI-Dateien aus laufendem Container sichern:  
   `docker cp crm-app-prod:/app/app/static/css/crm.css /opt/crm-prod/backups/ui-<TS>/`  
   (analog list/archived/dashboard/leads/tasks; Anrufliste ggf. „fehlte“)
3. SHA256 der Backup-Dateien dokumentieren

## Rollback-Befehl (atomar zum bisherigen Release)

```bash
# Auf WEB, nach vorherigem docker tag Backup:
docker tag crm-app-prod:pre-branding-ui-68ede4d crm-app-prod:local
cd /opt/crm-prod
docker compose -f docker-compose.production.yml --env-file .env.production up -d --force-recreate crm-app
curl -fsS https://crm.digitalehandwerkskunst.de/health
curl -fsS -o /dev/null -w '%{http_code}\n' https://crm.digitalehandwerkskunst.de/login
```

Alternativ file-level: `docker cp` der Backup-UI-Dateien zurück nach `/app/app/...` + `docker restart crm-app-prod`.

## Post-Deploy-Smoke-Plan (nach späterer Freigabe)

1. Health `env=production`, `ok=true`  
2. Login HTTP 200, STAGING-Badge **nicht** in Prod-Topbar  
3. CSS enthält `.table-wrap` und Mobile-Topbar-Regeln  
4. Unternehmen/Leads/Tasks/Dashboard/Archiv laden; Tabellen horizontal scrollen, keine Wortzerlegung  
5. Telefonie-Seite nur Layout; Dialer-Flags unverändert  
6. Alembic weiter `016_dl_meta_context`  
7. Keine neuen 5xx in Nginx/App-Log für UI-Routen  

## Execution-Skizze (noch nicht ausführen)

Nur nach expliziter Freigabe „deploy / live“:

1. Nur Release-Worktree `crm-release-68ede4d` verwenden  
2. Backup Image + UI-Dateien  
3. Entweder:
   - **A)** gezieltes Image-Rebuild mit unverändertem Prod-Build-Kontext außer den 7 UI-Dateien, **oder**
   - **B)** `docker cp` der 7 Dateien in `crm-app-prod:/app/app/...` + Restart  
4. **Kein** Alembic upgrade  
5. Smoke laut Plan  
6. Bei Fehler: Rollback-Befehl

## Stash-Suche (read-only, nichts verändert)

| Repo | Befund |
|------|--------|
| **CRM** (+ alle CRM-Worktrees) | `stash list` **leer**, `refs/stash` absent, kein Reflog-Treffer `wip-before-branding` |
| **webschmiede-server** | **gefunden:** `stash@{0}: wip-before-branding-pilot-step3` (`f110119`) |
| webschmiede-server | zusätzlich `stash@{1}: wip-non-entity-routing-before-rc-65a9393` |
| Hub | anderer Stash, unrelated |

**Erklärung:** Der gesuchte Stash liegt im **Server-Repo**, nicht im CRM. Frühere CRM-`stash list`-Leere war deshalb erwartbar. Nicht anwenden, nicht droppen, nicht mit Branding-Release vermischen.

## Dirty-Working-Tree-Bestätigung

| Tree | Dirty? | Für Deploy? |
|------|--------|-------------|
| `crm` (Main) | ja (~263) | **nein** |
| `crm-release-68ede4d` | nein | **ja (einzige Quelle)** |
| `crm-postmerge-ro` | nein @68ede4d | nicht nötig (Release-WT existiert) |
| `webschmiede-server` | ja (fremd) | nur Evidence; kein CRM-Code-Deploy |

## Offene Risiken vor Execution

1. Kein Bind-Mount: Host-Dateien unter `/opt/crm-prod/app` allein ändern den laufenden Container **nicht**  
2. Full-Build aus `68ede4d` würde Dialer/Sales-OS/Migrationen mitnehmen → strikt UI-only  
3. `anrufliste.html` ist neu auf Prod — nur Template; Route/Flags unverändert lassen  
4. Server-Stash `wip-before-branding-pilot-step3` bleibt separat  

## Evidence-Pfade

- `docs/platform-unification/evidence/limited-prod-prep/PREP.md` (diese Datei)
- `prod-inventory-ro.json`
- `prod-runtime-ro.json`
- `ui-hash-compare.json`
- `deploy-diff-ui-stat.txt` / `deploy-diff-ui-names.txt`
- `deploy-scope-guard.txt`
- `commits-between-prod-and-release.txt`
- `predeploy-pytest.txt` / `predeploy-import.txt` / `predeploy-compileall.txt` / `predeploy-jinja.txt`
- `secret-scan.txt`
- `stash-search-ro.txt`
- `scope-static-ok.txt`
