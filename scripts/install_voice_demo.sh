#!/usr/bin/env bash
# Webschmiede Voice Demo – NUR INSTALLIEREN, NICHT STARTEN.
#
# Was passiert:
#   - Docker/Compose prüfen
#   - Images pullen
#   - Gateway bauen
#   - Ollama-Modell und Whisper-Cache einmalig laden
#   - Am Ende: docker compose down (nichts bleibt laufend)
#
# Voraussetzung: Ubuntu, mind. 8 GB RAM (CX33), Ordner infra/voice-demo vorhanden.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEMO="$ROOT/infra/voice-demo"
MODEL="${OLLAMA_MODEL:-llama3.2:1b}"
WHISPER="${WHISPER_MODEL:-base}"
MARKER="$DEMO/.install-complete"

echo "=== Voice Demo INSTALL (kein Dauerbetrieb) ==="
echo "Ordner: $DEMO"
echo "LLM: $MODEL · Whisper: $WHISPER"

if [[ ! -d "$DEMO" ]]; then
  echo "FEHLER: $DEMO fehlt"
  exit 1
fi

MEM_KB=$(awk '/MemTotal/ {print $2}' /proc/meminfo)
MEM_GB=$((MEM_KB / 1024 / 1024))
echo "RAM: ${MEM_GB} GB"
if (( MEM_GB < 7 )); then
  echo "ABBRUCH: Mindestens 8 GB RAM noetig (gefunden: ${MEM_GB} GB)."
  echo "Nicht auf dem kleinen Shop-Server installieren."
  exit 2
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Installiere Docker…"
  apt-get update -y
  apt-get install -y ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
fi

docker --version
docker compose version

cd "$DEMO"
export OLLAMA_MODEL="$MODEL"
export WHISPER_MODEL="$WHISPER"

# Sicher: falls etwas lief, erst stoppen
docker compose down --remove-orphans 2>/dev/null || true

echo "→ Images pullen…"
docker compose pull ollama || true

echo "→ Gateway bauen (inkl. Python-Deps)…"
docker compose build gateway

echo "→ Ollama kurz hoch, Modell laden, wieder runter…"
docker compose up -d ollama
for i in $(seq 1 90); do
  if curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
docker compose exec -T ollama ollama pull "$MODEL"
if [[ "${PULL_EXTRA:-0}" == "1" ]]; then
  docker compose exec -T ollama ollama pull llama3.2:3b || true
fi

echo "→ Whisper-Modell in Cache ziehen (one-shot, kein Dauerbetrieb)…"
docker compose run --rm \
  -e WHISPER_MODEL="$WHISPER" \
  gateway \
  python -c "from faster_whisper import WhisperModel; import os; m=os.environ.get('WHISPER_MODEL','base'); print('loading', m); WhisperModel(m, device='cpu', compute_type='int8'); print('whisper_ok', m)"

echo "→ Alles wieder stoppen…"
docker compose down --remove-orphans

# Markierung: installiert, aber nicht gestartet
{
  echo "installed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "ollama_model=$MODEL"
  echo "whisper_model=$WHISPER"
  echo "status=installed_not_started"
} > "$MARKER"

echo
echo "=== FERTIG: installiert, nichts läuft ==="
docker compose ps -a || true
docker ps --format '{{.Names}}' | grep -iE 'voice|ollama|gateway' && echo "WARNUNG: noch Container aktiv" || echo "OK: keine Voice-Container aktiv"
echo "Marker: $MARKER"
echo "Spaeter starten: cd $DEMO && docker compose up -d"
