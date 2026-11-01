#!/usr/bin/env bash
# Idempotent Cloud-Agent bootstrap for Webschmiede Server (Flask API + static + agency-web).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! python3 -c "import venv" 2>/dev/null; then
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3.12-venv
fi

python3 -m venv "$ROOT/venv"
"$ROOT/venv/bin/pip" install -q --upgrade pip
"$ROOT/venv/bin/pip" install -q -r "$ROOT/app/backend/requirements.txt"

ENV_FILE="$ROOT/app/backend/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  cat > "$ENV_FILE" <<'EOF'
ADMIN_PASSWORD=dev-local-pass
PORTAL_MODE=gastro
KUNDE_ID=SHY001
GHL_ENABLED=false
SMS_ENABLED=false
PUSH_ENABLED=false
CORS_ORIGINS=http://127.0.0.1:8000,http://localhost:8000,http://127.0.0.1:8080,http://localhost:8080
PUBLIC_BASE_URL=http://127.0.0.1:8000
ORDER_PORTAL_URL=http://127.0.0.1:8080/order.html
EOF
fi

if [[ -f "$ROOT/agency-web/package-lock.json" ]]; then
  (cd "$ROOT/agency-web" && npm ci --no-fund --no-audit)
elif [[ -f "$ROOT/agency-web/package.json" ]]; then
  (cd "$ROOT/agency-web" && npm install --no-fund --no-audit)
fi

echo "cloud-agent-install: ok"
