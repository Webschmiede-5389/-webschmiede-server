# Hetzner 3-Server Setup (Webschmiede)

Stand: Juli 2026 · Migration vom Einzelserver `167.233.211.170`

## Bestellliste

| Hostname | Rolle | Hetzner-Typ | vCPU | RAM | Disk | Öffentlich |
|----------|-------|-------------|------|-----|------|------------|
| `web-01` | Nginx, API, Portale, Agency, Cal.com | **CX33** | 4 | 8 GB | 80 GB | ja |
| `auto-01` | n8n, Cron, Akquise, Watchdog | **CPX32** | 4 | 8 GB | 160 GB | optional SSH only |
| `db-01` | PostgreSQL, DB-Backups | **CX33** | 4 | 8 GB | 80 GB | **nein** |
| `voice-01` (optional) | Eigener Voice-Demo-Stack (Ollama + Whisper) | **CX32 / CX33** | 4 | **8 GB** (besser 16) | 80 GB | ja (8090 / Nginx) |

Alle: **Ubuntu 24.04 LTS**, gleiche **Region** (z. B. Falkenstein `fsn1` oder Nürnberg `nbg1`).

Optional später: `db-01` auf **CPX32** hochskalieren.

**Voice-Demo:** nicht auf dem kleinen Shop-Server (`167.233.211.170`, 2 GB). Siehe `infra/voice-demo/README.md` und `docs/agency/voice-agents.md`.

---

## vSwitch (privates Netz)

1. Hetzner Cloud Console → **Networks** → **Create Network**
2. Name: `webschmiede-private`
3. IP-Bereich: `10.0.0.0/24`

| Server | Private IP |
|--------|------------|
| web-01 | `10.0.0.2` |
| auto-01 | `10.0.0.3` |
| db-01 | `10.0.0.4` |

Jeden Server dem Network zuweisen.

---

## Firewall (Hetzner Cloud Firewall)

### web-01

| Richtung | Port | Quelle | Zweck |
|----------|------|--------|-------|
| in | 22 | deine IP /32 | SSH |
| in | 80 | 0.0.0.0/0 | HTTP |
| in | 443 | 0.0.0.0/0 | HTTPS |
| in | * | 10.0.0.0/24 | privates Netz |

### auto-01

| Richtung | Port | Quelle | Zweck |
|----------|------|--------|-------|
| in | 22 | deine IP /32 | SSH |
| in | 5678 | 10.0.0.2/32 | n8n nur von web-01 (Proxy) |
| in | * | 10.0.0.0/24 | privates Netz |

Kein öffentliches 80/443 auf auto-01 nötig.

### db-01

| Richtung | Port | Quelle | Zweck |
|----------|------|--------|-------|
| in | 22 | deine IP /32 | SSH Admin |
| in | 5432 | 10.0.0.2/32 | PostgreSQL von web-01 |
| in | 5432 | 10.0.0.3/32 | PostgreSQL von auto-01 |
| in | * | 10.0.0.0/24 | privates Netz |

**Kein** öffentliches 5432.

---

## Was auf welchen Server kommt

### web-01

- `/root/app/` (Repo, Flask `snack-api`, static)
- Nginx (alle Kunden-Domains, SSL)
- systemd `snack-api`
- Cal.com (Docker, optional später auf auto-01)
- `/var/www/...` Webroots
- Öffentliche Endpunkte: `/api/`, `/agency`, `/agency-setup`, Kundenportale

### auto-01

- n8n (`/opt/n8n`, systemd)
- Cron: Akquise, Follow-ups, Backup-Trigger, Watchdog
- `/root/app/scripts/`, `akquise/`
- Logs: `/var/log/akquise.log`, `/var/log/nightly-watchdog.log`
- Kein öffentlicher Kunden-Traffic

### db-01

- PostgreSQL 16
- DB-User nur von `10.0.0.2` und `10.0.0.3`
- Tägliche Dumps → Hetzner Storage Box oder Volume
- Keine App, kein n8n, kein Nginx

---

## DNS (nach Migration)

| Host | Ziel |
|------|------|
| `digitalehandwerkskunst.de` | web-01 öffentliche IP |
| `*.digitalehandwerkskunst.de` | web-01 (oder pro Kunde) |
| Kunden-Domains | web-01 |
| `cal.digitalehandwerkskunst.de` | web-01 |

n8n: `https://digitalehandwerkskunst.de/n8n/` → Proxy auf `http://10.0.0.3:5678/`

---

## Migrationsreihenfolge

1. 3 Server + vSwitch + Firewall anlegen
2. Alten Server vollständig sichern (siehe unten)
3. Basis auf allen 3 Servern (Ubuntu, Python, nginx nur web, Postgres nur db)
4. Code + Secrets auf web-01 und auto-01
5. PostgreSQL auf db-01, dann Datenmigration (SQLite → Postgres)
6. n8n + Cron auf auto-01
7. Nginx + SSL auf web-01, interne DB-URL `10.0.0.4`
8. Smoke-Tests (Bestellung, Agency Keys, n8n, Watchdog)
9. DNS umstellen
10. Alten Server 7 Tage behalten, dann löschen

---

## Backup vom alten Server (Checkliste)

Auf `167.233.211.170` sichern:

```bash
# Auf altem Server oder per rsync von lokal
tar czf backup-root-app.tar.gz /root/app
tar czf backup-var-www.tar.gz /var/www
tar czf backup-nginx.tar.gz /etc/nginx
tar czf backup-systemd.tar.gz /etc/systemd/system/snack-api.service /etc/systemd/system/n8n.service
tar czf backup-opt-n8n.tar.gz /opt/n8n
tar czf backup-opt-calcom.tar.gz /opt/calcom 2>/dev/null || true
crontab -l > crontab-root.txt
```

Lokal behalten (niemals ins Git):

- `deploy.secrets.local`
- `app/backend/.env` vom Server
- `n8n-credentials.local.txt`
- `agency-credentials.local.txt`

---

## Kosten grob

- 3 Server: ca. 35–55 €/Monat (CX33 + CPX32 + CX33)
- Storage Box 100 GB (Backups): ca. 3–5 €/Monat
- Alter CX11/CX21 kann als **Staging** bleiben oder gelöscht werden

---

## Skalierung später

| Trigger | Aktion |
|---------|--------|
| 20–30 Kunden | RAM auf 16 GB (web + db) |
| n8n unter Last | auto-01 → CPX größer oder CCX |
| 50+ Kunden | db-01 → CPX32/CPX42, web-02 optional |
| 100+ Kunden | Load Balancer + zweiter Web-Server |
