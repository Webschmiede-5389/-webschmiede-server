#!/usr/bin/env bash
# One-shot pull test: clone pinned branch/commit via read-only deploy key.
# Integrity: CHECKSUMS.sha256 (checksum only — not a cryptographic signature).
set -euo pipefail

RUN_ID="${1:-}"
EXPECTED_PUBLISH_COMMIT="${2:-}"
REPO="${PULL_TEST_REPO:-Webschmiede-5389/-webschmiede-server}"
BASE_DIR="${PULL_TEST_BASE_DIR:-/var/lib/webschmiede-pull-test}"
KEY_PATH="${PULL_TEST_DEPLOY_KEY:-/home/gha-deploy/.ssh/github_pull_readonly}"
KNOWN_HOSTS_PATH="${PULL_TEST_GITHUB_KNOWN_HOSTS:-/home/gha-deploy/.ssh/github_known_hosts}"
NEGATIVE_MODE="${PULL_TEST_NEGATIVE_MODE:-}"

if [[ -z "${RUN_ID}" || -z "${EXPECTED_PUBLISH_COMMIT}" ]]; then
  echo "Usage: $0 <github_run_id> <publish_commit_sha>" >&2
  exit 1
fi

# Reject path traversal and malformed pins before touching the filesystem.
if [[ ! "${RUN_ID}" =~ ^[1-9][0-9]*$ ]]; then
  echo "Invalid run ID: expected a positive decimal integer" >&2
  exit 9
fi
if [[ ! "${EXPECTED_PUBLISH_COMMIT}" =~ ^[0-9a-fA-F]{40}$ ]]; then
  echo "Invalid publish commit: expected a 40-character Git SHA-1" >&2
  exit 10
fi

if [[ "$(id -u)" -eq 0 ]]; then
  echo "Refusing to run as root" >&2
  exit 2
fi

if [[ ! -f "${KEY_PATH}" || ! -f "${KNOWN_HOSTS_PATH}" ]]; then
  echo "Missing deploy key or GitHub known_hosts" >&2
  exit 3
fi

if [[ "${NEGATIVE_MODE}" == "wrong_commit" ]]; then
  EXPECTED_PUBLISH_COMMIT="0000000000000000000000000000000000000000"
fi

BRANCH="hetzner-pull-test/run-${RUN_ID}"
# Use a new private directory each time; never delete a path derived from input.
# Reject a symlinked inbox so test data cannot escape the configured test root.
if [[ ! -d "${BASE_DIR}/inbox" || -L "${BASE_DIR}/inbox" ]]; then
  echo "Missing or symlinked pull-test inbox" >&2
  exit 11
fi
WORKDIR="$(mktemp -d "${BASE_DIR}/inbox/run-${RUN_ID}.XXXXXXXX")"
REPO_DIR="${WORKDIR}/repo"
ACTIVE_KNOWN_HOSTS="${KNOWN_HOSTS_PATH}"
chmod 700 "${WORKDIR}"

if [[ "${NEGATIVE_MODE}" == "bad_hostkey" ]]; then
  ACTIVE_KNOWN_HOSTS="${WORKDIR}/bad_known_hosts"
  printf '%s\n' "github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBogfakefakefakefakefakefakefakefakefakefakef" > "${ACTIVE_KNOWN_HOSTS}"
  chmod 600 "${ACTIVE_KNOWN_HOSTS}"
fi

export GIT_SSH_COMMAND="ssh -i ${KEY_PATH} -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=${ACTIVE_KNOWN_HOSTS} -o BatchMode=yes"

if [[ "${NEGATIVE_MODE}" == "bad_hostkey" ]]; then
  if git clone --depth 1 --branch "${BRANCH}" "git@github.com:${REPO}.git" "${REPO_DIR}" 2>/dev/null; then
    echo "negative test failed: bad hostkey allowed clone" >&2
    exit 20
  fi
  echo "negative_test_ok=1 mode=bad_hostkey"
  exit 0
fi

git clone --depth 1 --branch "${BRANCH}" "git@github.com:${REPO}.git" "${REPO_DIR}"

ACTUAL_HEAD="$(git -C "${REPO_DIR}" rev-parse HEAD)"
if [[ "${ACTUAL_HEAD}" != "${EXPECTED_PUBLISH_COMMIT}" ]]; then
  echo "publish commit pin mismatch expected=${EXPECTED_PUBLISH_COMMIT} actual=${ACTUAL_HEAD}" >&2
  if [[ "${NEGATIVE_MODE}" == "wrong_commit" ]]; then
    echo "negative_test_ok=1 mode=wrong_commit"
    exit 0
  fi
  exit 7
fi

CLONED_BRANCH="$(git -C "${REPO_DIR}" branch --show-current)"
if [[ "${CLONED_BRANCH}" != "${BRANCH}" ]]; then
  echo "branch mismatch expected=${BRANCH} actual=${CLONED_BRANCH}" >&2
  exit 8
fi

PAYLOAD="${REPO_DIR}/pull-test-payload"
cd "${PAYLOAD}"

sha256sum -c CHECKSUMS.sha256

SOURCE_SHA="$(tr -d '\r\n' < source_workflow_sha.txt)"
RUN_FILE="$(tr -d '\r\n' < run_id.txt)"

if [[ "${RUN_FILE}" != "${RUN_ID}" ]]; then
  echo "run_id mismatch" >&2
  exit 5
fi

python3 - <<'PY' "${ACTUAL_HEAD}" "${SOURCE_SHA}" "${RUN_ID}"
import json, sys
publish_pin, source_sha, run_id = sys.argv[1], sys.argv[2], sys.argv[3]
manifest = json.load(open("manifest.json", encoding="utf-8"))
if manifest.get("source_workflow_sha") != source_sha:
    raise SystemExit("manifest source_workflow_sha mismatch")
if str(manifest.get("run_id")) != str(run_id):
    raise SystemExit("manifest run_id mismatch")
if manifest.get("channel") != "hetzner-pull-test":
    raise SystemExit("manifest channel mismatch")
if manifest.get("integrity") != "checksum-only":
    raise SystemExit("manifest integrity label mismatch")
print("manifest_ok=1")
PY

if [[ "${NEGATIVE_MODE}" == "tamper" ]]; then
  echo "tamper" >> source_workflow_sha.txt
  if sha256sum -c CHECKSUMS.sha256; then
    echo "negative test failed: checksum should not pass after tamper" >&2
    exit 6
  fi
  echo "negative_test_ok=1 mode=tamper"
  exit 0
fi

echo "pull_ok=1 host=$(hostname -s) user=$(whoami) run_id=${RUN_ID} publish_commit=${ACTUAL_HEAD} checksum_verified=1"
