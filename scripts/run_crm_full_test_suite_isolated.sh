#!/usr/bin/env bash
# Isolated CRM full test suite — blocks Production/Staging DBs and live providers.
# Usage (from CRM repo root OR via --crm-root):
#   bash scripts/run_crm_full_test_suite_isolated.sh
#   bash /path/to/webschmiede-server/scripts/run_crm_full_test_suite_isolated.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Prefer sibling CRM; allow override
CRM_ROOT="${CRM_ROOT:-}"
if [[ -z "${CRM_ROOT}" ]]; then
  if [[ -d "${SCRIPT_DIR}/../crm" ]]; then
    CRM_ROOT="$(cd "${SCRIPT_DIR}/../crm" && pwd)"
  elif [[ -f "${SCRIPT_DIR}/../requirements.txt" && -d "${SCRIPT_DIR}/../alembic" ]]; then
    CRM_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
  else
    echo "Set CRM_ROOT to the CRM repository root" >&2
    exit 2
  fi
fi

cd "${CRM_ROOT}"
EVIDENCE_DIR="${EVIDENCE_DIR:-}"
if [[ -z "${EVIDENCE_DIR}" ]]; then
  SERVER_DOCS="$(cd "${SCRIPT_DIR}/.." && pwd)/docs/platform-unification/evidence/step-4"
  if [[ -d "$(dirname "${SERVER_DOCS}")" ]]; then
    EVIDENCE_DIR="${SERVER_DOCS}"
  else
    EVIDENCE_DIR="${CRM_ROOT}/.step4-evidence"
  fi
fi
mkdir -p "${EVIDENCE_DIR}"
OUT_FILE="${1:-${EVIDENCE_DIR}/full-suite-run.txt}"

VENV="${CRM_ROOT}/.venv-step4"
if [[ ! -x "${VENV}/bin/python" && ! -x "${VENV}/Scripts/python.exe" ]]; then
  echo "Creating ${VENV}"
  python3 -m venv "${VENV}" 2>/dev/null || python -m venv "${VENV}"
fi
if [[ -x "${VENV}/Scripts/python.exe" ]]; then
  PY="${VENV}/Scripts/python.exe"
  PIP="${VENV}/Scripts/pip.exe"
else
  PY="${VENV}/bin/python"
  PIP="${VENV}/bin/pip"
fi

"${PIP}" install -q -U pip
"${PIP}" install -q -r requirements.txt

# Site-packages FIRST so local ./alembic migrations dir does not shadow the alembic package
SP="$("${PY}" -c "import site; print(site.getsitepackages()[0])")"
export PYTHONPATH="${SP}${PYTHONPATH:+:${PYTHONPATH}}"

# --- hard isolation ---
unset DATABASE_URL || true
unset CRM_TEST_DATABASE_URL || true
export APP_ENV=test
export CRM_TEST_DIALECT=sqlite
export ALLOW_CREATE_ALL=true
export CSRF_ENABLED=false
export RATE_LIMIT_ENABLED=false
export OUTBOUND_ENABLED=false
export SALES_OUTBOUND_ENABLED=false
export N8N_ENABLED=false
export NILS_WRITE_ENABLED=false
export EMAIL_SEND_ENABLED=false
export WHATSAPP_SEND_ENABLED=false
export PHONE_INTEGRATION_ENABLED=false
export PLACETEL_ENABLED=false
export PLACETEL_CLICK_TO_DIAL_ENABLED=false
export PLACETEL_WEBHOOKS_ENABLED=false
export CALL_RECORDING_ENABLED=false
export LIVE_TRANSCRIPTION_ENABLED=false

# Block obvious production URLs if someone exports them
if [[ -n "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL must be unset for isolated suite" >&2
  exit 3
fi
if [[ -n "${CRM_TEST_DATABASE_URL:-}" ]]; then
  case "${CRM_TEST_DATABASE_URL}" in
    *prod*|*production*|*hetzner*|*digitalehandwerkskunst*|*crm-db*)
      echo "CRM_TEST_DATABASE_URL looks unsafe — abort" >&2
      exit 3
      ;;
  esac
fi

START_ISO="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
COMMIT="$("${PY}" -c "import subprocess; print(subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip())")"
PYVER="$("${PY}" -c "import sys; print(sys.version.split()[0])")"

{
  echo "=== CRM isolated full suite ==="
  echo "start_utc=${START_ISO}"
  echo "crm_root=${CRM_ROOT}"
  echo "commit=${COMMIT}"
  echo "python=${PYVER}"
  echo "venv=${VENV}"
  echo "PYTHONPATH_prefix=${SP}"
  echo "APP_ENV=${APP_ENV}"
  echo "CRM_TEST_DIALECT=${CRM_TEST_DIALECT}"
  echo "providers=disabled"
  echo "command=${PY} -m pytest tests/ -q --tb=line"
  echo "=== BEGIN pytest ==="
} > "${OUT_FILE}"

set +e
"${PY}" -m pytest tests/ -q --tb=line 2>&1 | tee -a "${OUT_FILE}"
CODE=${PIPESTATUS[0]:-$?}
set -e

{
  echo "=== END pytest ==="
  echo "exit_code=${CODE}"
  echo "end_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} >> "${OUT_FILE}"

echo "Wrote ${OUT_FILE} (exit ${CODE})"
exit "${CODE}"
