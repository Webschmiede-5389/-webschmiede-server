#!/usr/bin/env bash
# One-shot pull test: clone explicit hetzner-pull-test/run-<RUN_ID> branch via read-only deploy key.
# No production paths touched. Run as gha-deploy.
set -euo pipefail

RUN_ID="${1:-}"
REPO="${PULL_TEST_REPO:-Webschmiede-5389/-webschmiede-server}"
BASE_DIR="${PULL_TEST_BASE_DIR:-/var/lib/webschmiede-pull-test}"
KEY_PATH="${PULL_TEST_DEPLOY_KEY:-/home/gha-deploy/.ssh/github_pull_readonly}"
NEGATIVE_TEST="${PULL_TEST_NEGATIVE_TEST:-0}"

if [[ -z "${RUN_ID}" ]]; then
  echo "Usage: $0 <github_run_id>" >&2
  exit 1
fi

if [[ "$(id -u)" -eq 0 ]]; then
  echo "Refusing to run as root" >&2
  exit 2
fi

if [[ ! -f "${KEY_PATH}" ]]; then
  echo "Missing deploy key: ${KEY_PATH}" >&2
  exit 3
fi

BRANCH="hetzner-pull-test/run-${RUN_ID}"
WORKDIR="${BASE_DIR}/inbox/run-${RUN_ID}"
REPO_DIR="${WORKDIR}/repo"

rm -rf "${WORKDIR}"
mkdir -p "${WORKDIR}"
chmod 700 "${BASE_DIR}" "${WORKDIR}" 2>/dev/null || true

export GIT_SSH_COMMAND="ssh -i ${KEY_PATH} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -o BatchMode=yes"

git clone --depth 1 --branch "${BRANCH}" "git@github.com:${REPO}.git" "${REPO_DIR}"

PAYLOAD="${REPO_DIR}/pull-test-payload"
if [[ ! -d "${PAYLOAD}" ]]; then
  echo "Missing payload directory" >&2
  exit 4
fi

cd "${PAYLOAD}"
sha256sum -c SHA256SUMS

COMMIT_SHA="$(tr -d '\r\n' < commit_sha.txt)"
RUN_FILE="$(tr -d '\r\n' < run_id.txt)"

if [[ "${RUN_FILE}" != "${RUN_ID}" ]]; then
  echo "run_id mismatch" >&2
  exit 5
fi

python3 - <<'PY' "${COMMIT_SHA}" "${RUN_ID}"
import json, sys
commit_sha, run_id = sys.argv[1], sys.argv[2]
manifest = json.load(open("manifest.json", encoding="utf-8"))
if manifest.get("commit_sha") != commit_sha:
    raise SystemExit("manifest commit_sha mismatch")
if str(manifest.get("run_id")) != str(run_id):
    raise SystemExit("manifest run_id mismatch")
if manifest.get("channel") != "hetzner-pull-test":
    raise SystemExit("manifest channel mismatch")
print("manifest_ok=1")
PY

if [[ "${NEGATIVE_TEST}" == "1" ]]; then
  echo "tamper" >> commit_sha.txt
  if sha256sum -c SHA256SUMS; then
    echo "negative test failed: checksum should not pass after tamper" >&2
    exit 6
  fi
  echo "negative_test_ok=1"
  exit 0
fi

echo "pull_ok=1 host=$(hostname -s) run_id=${RUN_ID} commit_sha=${COMMIT_SHA}"
