#!/usr/bin/env bash
# Install read-only GitHub deploy key + verified github.com known_hosts for gha-deploy.
set -euo pipefail

DEPLOY_USER="${DEPLOY_USER:-gha-deploy}"
KEY_SRC="${1:-}"
KNOWN_HOSTS_SRC="${2:-}"

if [[ -z "${KEY_SRC}" || ! -f "${KEY_SRC}" ]]; then
  echo "Usage: $0 /path/to/github_pull_readonly_private_key /path/to/github_ssh_known_hosts" >&2
  exit 1
fi

if [[ -z "${KNOWN_HOSTS_SRC}" || ! -f "${KNOWN_HOSTS_SRC}" ]]; then
  echo "Missing github_ssh_known_hosts source file" >&2
  exit 1
fi

if ! id "${DEPLOY_USER}" &>/dev/null; then
  echo "User ${DEPLOY_USER} missing — run bootstrap-gha-deploy-user.sh first" >&2
  exit 2
fi

# Strip comments; require github.com lines
mapfile -t HOST_LINES < <(grep -E '^github\.com ' "${KNOWN_HOSTS_SRC}" || true)
if [[ "${#HOST_LINES[@]}" -lt 1 ]]; then
  echo "No github.com host keys in ${KNOWN_HOSTS_SRC}" >&2
  exit 3
fi

install -d -m 700 -o "${DEPLOY_USER}" -g "${DEPLOY_USER}" "/home/${DEPLOY_USER}/.ssh"
install -m 600 -o "${DEPLOY_USER}" -g "${DEPLOY_USER}" "${KEY_SRC}" "/home/${DEPLOY_USER}/.ssh/github_pull_readonly"
{
  for line in "${HOST_LINES[@]}"; do
    printf '%s\n' "${line}"
  done
} > "/home/${DEPLOY_USER}/.ssh/github_known_hosts"
chown "${DEPLOY_USER}:${DEPLOY_USER}" "/home/${DEPLOY_USER}/.ssh/github_known_hosts"
chmod 600 "/home/${DEPLOY_USER}/.ssh/github_known_hosts"

install -d -m 700 -o "${DEPLOY_USER}" -g "${DEPLOY_USER}" /var/lib/webschmiede-pull-test/inbox
install -d -m 700 -o "${DEPLOY_USER}" -g "${DEPLOY_USER}" /var/lib/webschmiede-pull-test/work

echo "OK host=$(hostname -s) user=${DEPLOY_USER} key_installed=1 known_hosts_lines=${#HOST_LINES[@]}"
