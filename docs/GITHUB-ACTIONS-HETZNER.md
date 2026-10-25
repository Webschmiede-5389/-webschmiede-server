# GitHub Actions ↔ Hetzner (SSH-Preflight)

Scope: `SHARED_INFRA` · Repos `Webschmiede-5389/-webschmiede-server` · **kein Produkt-Deploy** in Phase 1.

## Serverzuordnung

| Rolle | Hetzner-Name | Hostname | IPv4 | Zweck |
|-------|----------------|----------|------|--------|
| WEB | Voice01neu | `web-01neu` | `167.233.150.230` | Web, Apps, Kundendaten |
| AUTO | Auto-01neu | `Auto-01neu` | `88.198.170.156` | n8n, Automatisierung |

## Zugriffsmodell (Ziel)

| Kanal | User | Auth | CI-tauglich |
|-------|------|------|-------------|
| Operator / `deploy.py` | `root` | Passwort in `deploy.secrets.local` | **nein** (Hub: SSH-Keys, keine Root-Passwörter in Repos) |
| GitHub Actions | `gha-deploy` | dedizierter **ed25519**-Deploy-Key | **ja** (nur Preflight, später eingeschränktes Deploy) |

Öffentlicher CI-Key (Referenz): `infra/github-actions/gha-deploy.pub`  
Fingerprint: `SHA256:Wr+QbFp7/Iq/1SZ+0ndzdnhnu0sPrn0kOBC1V6pZsYY`

## Freigabe A — Server (je Host einmal, als root)

Keine Dienste neu starten, keine App-Updates.

```bash
# Auf web-01neu und Auto-01neu (Datei z. B. nach /tmp/gha-deploy.pub kopieren):
bash scripts/infra/bootstrap-gha-deploy-user.sh /tmp/gha-deploy.pub
```

Optional testen (Operator-SSH):

```bash
ssh gha-deploy@167.233.150.230 'hostname; id -u'
ssh gha-deploy@88.198.170.156 'hostname; id -u'
```

## Freigabe B — GitHub Environments + Secrets

Repository: `Webschmiede-5389/-webschmiede-server`  
Environments anlegen: `hetzner-web`, `hetzner-auto` (optional: Required reviewers).

| Secret | Environment | Inhalt |
|--------|-------------|--------|
| `HETZNER_GHA_DEPLOY_SSH_USER` | beide (repo-level ok) | `gha-deploy` |
| `HETZNER_GHA_DEPLOY_SSH_PRIVATE_KEY` | beide | privater ed25519-Key (**nicht** Bitwarden-Personalkey) |
| `HETZNER_SSH_HOST` | `hetzner-web` | `167.233.150.230` |
| `HETZNER_SSH_HOST` | `hetzner-auto` | `88.198.170.156` |
| `HETZNER_SSH_KNOWN_HOSTS` | beide (gleicher Wert oder je Environment) | `ssh-keyscan -t ed25519,rsa 167.233.150.230 88.198.170.156` (Linux) |

Private Key liegt nur lokal unter `tmp/hetzner-gha-deploy-key/` (gitignored) bis er in GitHub Secrets gesetzt ist.

## Workflow

- Datei: `.github/workflows/hetzner-ssh-preflight.yml`
- Manuell: Actions → **Hetzner SSH preflight** → Run workflow
- Erfolg: beide Matrix-Ziele melden `preflight_ok=1`, `uid` ≠ 0, Hostname passt

## Was Phase 1 ausdrücklich nicht tut

- Kein `deploy.py`, kein rsync, kein Docker-Compose-Reload
- Keine DB- oder nginx-Änderungen
- Kein Merge ohne separate Freigabe
