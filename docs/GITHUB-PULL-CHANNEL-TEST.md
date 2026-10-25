# GitHub → Hetzner Pull-Kanal (Test)

Scope: `SHARED_INFRA` · manueller **`workflow_dispatch`** · kein Produkt-Deploy.

## Warum Pull?

Hetzner Cloud Firewall `webschmiede-dual` blockiert Inbound-SSH von GitHub-hosted Runnern. WEB/AUTO holen Teststände **ausgehend** per Git/SSH zu `github.com`.

## Veröffentlichung (GitHub)

Workflow: `.github/workflows/hetzner-pull-channel-test.yml`

- Pro Run **ein neuer** Branch `hetzner-pull-test/run-<RUN_ID>` — **kein** `--force` (bestehende Branches werden nicht überschrieben).
- Server-Pin: **`publish_commit`** (Git-HEAD des Publish-Branches), zusätzlich `source_workflow_sha` (Workflow-Auslöser-Commit).
- `CHECKSUMS.sha256`: **Integritäts-Prüfsummen**, **keine** kryptografische Signatur. Kein `SIGNATURE_VERIFIED`-Claim.
- Für spätere Produktiv-Releases wären getrennt zu prüfen: GitHub Artifact Attestations / signierte Release-Artefakte (nicht Teil dieses Tests).

## Server-Abruf

```bash
# als gha-deploy, einmalig manuell:
pull-github-channel-test.sh <RUN_ID> <PUBLISH_COMMIT_SHA>
```

- GitHub-Hostkeys: `infra/github-actions/github_ssh_known_hosts` (Fingerprints gegen `api.github.com/meta` abgleichen).
- SSH: `StrictHostKeyChecking=yes`, kein `accept-new`.
- Isoliertes Verzeichnis: `/var/lib/webschmiede-pull-test/inbox/`.

## Negativtests (manuell)

| Modus | Env |
|-------|-----|
| Manipulation | `PULL_TEST_NEGATIVE_MODE=tamper` |
| Falscher Host-Key | `PULL_TEST_NEGATIVE_MODE=bad_hostkey` |
| Falscher Commit-Pin | `PULL_TEST_NEGATIVE_MODE=wrong_commit` |

## Sicherheit

- Read-only Deploy Key (kein breites PAT)
- Keine Firewall-Aufweitung, kein Self-hosted Runner, kein Cron/systemd in der Testphase
