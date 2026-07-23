# PostgreSQL-Migrationsplan (Webschmiede)

**Stand:** Juli 2026 · **Jetzt:** SQLite auf einem Server · **Ziel:** dedizierter `db-01` wenn Kunden + Budget da sind.

## Warum später Postgres

- Mehrere Kunden-Instanzen / Tenants auf einem API-Cluster
- Bessere Nebenläufigkeit als SQLite bei vielen Schreibzugriffen
- Zentrale Backups, Replikation, Monitoring

## Was bleibt vorerst SQLite

| Bereich | Grund |
|---------|-------|
| 0–3 Live-Kunden auf einem CX33 | SQLite reicht, weniger Ops |
| Nacht-Jobs, Akquise-Reports | Dateien + eigene DBs |
| Agency-Metriken (`ops_events`) | Klein, lokal |

## Migrations-Trigger (mindestens eines)

1. **≥ 5 aktive Kunden** mit eigenem Order-Volume
2. **DB > 500 MB** oder spürbare Lock-Wartezeiten
3. **Zweiter App-Server** (`web-01` + `auto-01`) braucht gemeinsame DB
4. **CX33** oder größer bestellt (siehe `docs/agency/hetzner-3-server.md`)

## Ziel-Architektur

```
web-01 (CX33)     → Flask/Gunicorn, Static
auto-01 (CPX32)   → n8n, Cron, Akquise
db-01 (CX33)      → PostgreSQL 16, nur private IP
```

## Schema-Mapping (SQLite → Postgres)

| SQLite | Postgres |
|--------|----------|
| `orders` | `orders` (+ `kunde_id` TEXT NOT NULL) |
| `contacts` | `contacts` (+ `kunde_id`) |
| `message_log` | `message_log` |
| `ops_events` | `ops_events` |
| `ops_metrics_daily` | `ops_metrics_daily` |
| `settings` | `tenant_settings` (key, value, kunde_id) |
| `INTEGER PRIMARY KEY AUTOINCREMENT` | `SERIAL` / `BIGSERIAL` |
| `datetime('now')` | `NOW() AT TIME ZONE 'UTC'` |

## Migrations-Schritte (wenn ausgelöst)

1. **Postgres auf db-01** installieren, nur VPC/Firewall von web + auto
2. **Alembic oder SQL-Skripte** aus `init_db()` in `main.py` ableiten
3. **Dual-Write Phase** (optional): neue Orders in beide DBs, vergleichen
4. **Einmal-Export:** `sqlite3 orders.db .dump` → bereinigen → `psql` import
5. **`DATABASE_URL`** in `.env`, Connection-Pool in Flask
6. **Backup:** `pg_dump` täglich → gleicher Off-Server-Pfad wie `backup_agency.sh`
7. **Watchdog:** Marker `postgres backup ok` in `/var/log/snack-backup.log`

## Env (Ziel)

```env
DATABASE_URL=postgresql://webschmiede:***@10.0.0.3:5432/agency
KUNDEN_DIR=/root/app/kunden
KNOWLEDGE_DIR=/root/app/knowledge
```

## Multi-Tenant ohne Postgres (Zwischenstufe)

- Pro Kunde eigene `orders_{kid}.db` auf demselben Server
- `KUNDE_ID` in `.env` pro Subdomain (bereits teilweise so)
- Agency-Cockpit aggregiert Health; Metriken mit `kunde_id` in `ops_events`

## Nicht migrieren

- Akquise-JSON-Reports (`docs/akquise/reports/`)
- n8n interne SQLite
- Statische Sites in `/var/www/`

## Checkliste vor Go-Live Postgres

- [ ] Load-Test: 20 parallele Bestellungen ohne Lock-Fehler
- [ ] Restore-Test aus `pg_dump` auf Staging
- [ ] `nightly_watchdog` prüft DB-Backup-Marker
- [ ] Rollback-Plan: `DATABASE_URL` zurück auf SQLite-Datei
