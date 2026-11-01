#!/usr/bin/env bash
# Per-boot Cloud-Agent start: snack-api (8000) + static portal (8080).
# Keeps a foreground process so the environment start phase stays attached.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export ADMIN_PASSWORD="${ADMIN_PASSWORD:-dev-local-pass}"
export PORTAL_MODE="${PORTAL_MODE:-gastro}"
export KUNDE_ID="${KUNDE_ID:-SHY001}"
export GHL_ENABLED="${GHL_ENABLED:-false}"
export SMS_ENABLED="${SMS_ENABLED:-false}"
export PUSH_ENABLED="${PUSH_ENABLED:-false}"
export CORS_ORIGINS="${CORS_ORIGINS:-http://127.0.0.1:8000,http://localhost:8000,http://127.0.0.1:8080,http://localhost:8080}"
export PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-http://127.0.0.1:8000}"

PYTHON="$ROOT/venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  echo "cloud-agent-start: missing venv at $ROOT/venv — run install first" >&2
  exit 1
fi

pid_on_port() {
  local port="$1"
  ss -ltnp 2>/dev/null | awk -v p=":$port" '$4 ~ p {print; exit}' | sed -n 's/.*pid=\([0-9]*\).*/\1/p'
}

wait_http() {
  local url="$1"
  local n=0
  while (( n < 40 )); do
    if curl -sf "$url" >/dev/null; then
      return 0
    fi
    sleep 0.25
    n=$((n + 1))
  done
  return 1
}

# API on :8000
if ! curl -sf http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
  old="$(pid_on_port 8000 || true)"
  if [[ -n "${old:-}" ]]; then
    kill "$old" 2>/dev/null || true
    sleep 0.5
  fi
  (
    cd "$ROOT/app/backend"
    exec "$PYTHON" -c "from main import app; app.run(host='0.0.0.0', port=8000, debug=False, use_reloader=False)"
  ) > /tmp/snack-api.log 2>&1 &
  echo $! > /tmp/snack-api.pid
  if ! wait_http http://127.0.0.1:8000/api/health; then
    echo "cloud-agent-start: API failed to become ready" >&2
    tail -n 40 /tmp/snack-api.log >&2 || true
    exit 1
  fi
fi

# Static files on :8080 (order/admin HTML)
if curl -sf -o /dev/null http://127.0.0.1:8080/order.html 2>/dev/null; then
  echo "cloud-agent-start: static already up on :8080"
  # Keep attached by following API log
  touch /tmp/snack-api.log
  exec tail -F /tmp/snack-api.log
fi

old_static="$(pid_on_port 8080 || true)"
if [[ -n "${old_static:-}" ]]; then
  kill "$old_static" 2>/dev/null || true
  sleep 0.5
fi

cd "$ROOT/app/static"
echo "cloud-agent-start: API :8000 ok, serving static on :8080"
exec "$PYTHON" -m http.server 8080 --bind 0.0.0.0
