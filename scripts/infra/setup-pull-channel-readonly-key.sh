#!/usr/bin/env bash
# Install read-only GitHub deploy private key for gha-deploy (pull-test only).
# Run as root once per host. Does not modify webschmiede-dual or sshd.
set -euo pipefail

DEPLOY_USER="${DEPLOY_USER:-gha-deploy}"
KEY_SRC="${1:-}"

if [[ -z "${KEY_SRC}" || ! -f "${KEY_SRC}" ]]; then
  echo "Usage: $0 /path/to/github_pull_readonly_private_key" >&2
  exit 1
fi

if ! id "${DEPLOY_USER}" &>/dev/null; then
  echo "User ${DEPLOY_USER} missing — run bootstrap-gha-deploy-user.sh first" >&2
  exit 2
fi

install -d -m 700 -o "${DEPLOY_USER}" -g "${DEPLOY_USER}" "/home/${DEPLOY_USER}/.ssh"
install -m 600 -o "${DEPLOY_USER}" -g "${DEPLOY_USER}" "${KEY_SRC}" "/home/${DEPLOY_USER}/.ssh/github_pull_readonly"

install -d -m 700 -o "${DEPLOY_USER}" -g "${DEPLOY_USER}" /var/lib/webschmiede-pull-test/inbox
install -d -m 700 -o "${DEPLOY_USER}" -g "${DEPLOY_USER}" /var/lib/webschmiede-pull-test/work

echo "OK host=$(hostname -s) user=${DEPLOY_USER} key_installed=1 base_dir=/var/lib/webschmiede-pull-test"
