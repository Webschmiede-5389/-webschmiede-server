# GitHub → Hetzner Pull-Kanal (Test)

Scope: `SHARED_INFRA` · manueller **workflow_dispatch** · kein Produkt-Deploy.

## Warum Pull?

Hetzner Cloud Firewall `webschmiede-dual` erlaubt SSH/22 nur für eine feste Allowlist — **nicht** für GitHub-hosted Runner. Statt Inbound-SSH von GHA holen WEB/AUTO das Test-Artefakt **ausgehend per HTTPS/Git (Port 443/22 zu github.com)**.

## GitHub

Workflow: `.github/workflows/hetzner-pull-channel-test.yml`

- Nur **manuell** (`workflow_dispatch`)
- Erzeugt Branch `hetzner-pull-test/run-<RUN_ID>` mit Verzeichnis `pull-test-payload/` (Manifest, Dateien, `SHA256SUMS`)
- Kein Merge in `main`, kein automatisches Deploy

## Server

- User: **`gha-deploy`** (kein Root)
- Read-only **Deploy Key** (nur Repo-Clone): `infra/github-actions/github-pull-readonly.pub`
- Basisverzeichnis: `/var/lib/webschmiede-pull-test/inbox/` (isoliert)
- Skripte:
  - `scripts/infra/setup-pull-channel-readonly-key.sh` (einmalig, root)
  - `scripts/infra/pull-github-channel-test.sh <RUN_ID>` (einmalig, als `gha-deploy`)

## Einmaliger Testablauf

1. Workflow auf Feature-Branch starten → `RUN_ID` notieren
2. Auf WEB und AUTO: `pull-github-channel-test.sh <RUN_ID>`
3. Optional Negativtest: `PULL_TEST_NEGATIVE_TEST=1 pull-github-channel-test.sh <RUN_ID>`

## Sicherheit

- Deploy Key: **read-only**, kein Actions-Scope, kein breites PAT
- Keine Änderung an `webschmiede-dual`
- Kein Cron, kein systemd-Timer in der Testphase
