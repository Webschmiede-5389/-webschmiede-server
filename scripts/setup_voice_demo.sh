#!/usr/bin/env bash
# Installiert den Webschmiede Voice-Demo-Stack (ohne Retell).
# Voraussetzung: Ubuntu 24.04, Docker, mind. 4 vCPU / 8 GB RAM.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEMO="$ROOT/infra/voice-demo"
MODEL="${OLLAMA_MODEL:-llama3.2:1b}"
WHISPER="${WHISPER_MODEL:-base}"

echo "=== Webschmiede Voice Demo Setup ==="
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
  echo "Diesen Stack NICHT auf dem kleinen Shop-Server starten."
  exit 2
fi

cd "$DEMO"
export OLLAMA_MODEL="$MODEL"
export WHISPER_MODEL="$WHISPER"
docker compose pull ollama || true
docker compose build gateway
docker compose up -d

echo "Warte auf Ollama…"
for i in $(seq 1 60); do
  if curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "Lade Modell $MODEL …"
docker compose exec -T ollama ollama pull "$MODEL"

echo "Health Gateway:"
curl -sf http://127.0.0.1:8090/api/health || true
echo
echo "Fertig. UI: http://SERVER-IP:8090/"
echo "Spaeter Nginx/SSL davor setzen (z. B. voice.digitalehandwerkskunst.de)."
