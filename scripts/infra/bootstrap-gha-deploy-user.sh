#!/usr/bin/env bash
# Bootstrap restricted GitHub Actions SSH user (read-only connection test phase).
# Run as root on each target host. Does NOT restart services or change apps.
set -euo pipefail

DEPLOY_USER="${DEPLOY_USER:-gha-deploy}"
PUBKEY_FILE="${1:-}"

if [[ -z "${PUBKEY_FILE}" || ! -f "${PUBKEY_FILE}" ]]; then
  echo "Usage: $0 /path/to/gha-deploy.pub" >&2
  exit 1
fi

if ! id "${DEPLOY_USER}" &>/dev/null; then
  useradd -m -s /bin/bash -U "${DEPLOY_USER}"
  echo "Created user ${DEPLOY_USER}"
else
  echo "User ${DEPLOY_USER} already exists"
fi

passwd -l "${DEPLOY_USER}" 2>/dev/null || true

install -d -m 700 -o "${DEPLOY_USER}" -g "${DEPLOY_USER}" "/home/${DEPLOY_USER}/.ssh"
AUTH="/home/${DEPLOY_USER}/.ssh/authorized_keys"
touch "${AUTH}"
chmod 600 "${AUTH}"
chown "${DEPLOY_USER}:${DEPLOY_USER}" "${AUTH}"

PUBKEY_LINE="$(grep -v '^[[:space:]]*#' "${PUBKEY_FILE}" | grep -v '^[[:space:]]*$' | head -n1)"
if [[ -z "${PUBKEY_LINE}" ]]; then
  echo "No public key line in ${PUBKEY_FILE}" >&2
  exit 1
fi

if ! grep -qF "${PUBKEY_LINE}" "${AUTH}"; then
  echo "${PUBKEY_LINE}" >> "${AUTH}"
  echo "Appended deploy public key to ${AUTH}"
else
  echo "Deploy public key already present in ${AUTH}"
fi

# Connection-test sanity (no deploy permissions yet)
if id -u "${DEPLOY_USER}" | grep -qx '0'; then
  echo "Refusing root-equivalent deploy user" >&2
  exit 1
fi

echo "OK host=$(hostname -f) user=${DEPLOY_USER} uid=$(id -u "${DEPLOY_USER}")"
