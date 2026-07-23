#!/usr/bin/env bash
# Lädt Modelle vor, sobald ein Server mit genug RAM da ist.
# NICHT auf dem 2-GB-Shop-Server ausführen.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEMO="$ROOT/infra/voice-demo"
MODEL="${OLLAMA_MODEL:-llama3.2:1b}"
WHISPER="${WHISPER_MODEL:-base}"

MEM_KB=$(awk '/MemTotal/ {print $2}' /proc/meminfo)
MEM_GB=$((MEM_KB / 1024 / 1024))
if (( MEM_GB < 7 )); then
  echo "ABBRUCH: Prefetch braucht mind. 8 GB RAM (gefunden: ${MEM_GB} GB)."
  exit 2
fi

cd "$DEMO"
docker compose up -d ollama
echo "Warte auf Ollama…"
for i in $(seq 1 60); do
  curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break
  sleep 2
done

echo "Lade LLM: $MODEL"
docker compose exec -T ollama ollama pull "$MODEL"

# optionales zweites Modell fuer bessere Qualitaet
if [[ "${PULL_EXTRA:-0}" == "1" ]]; then
  echo "Lade Extra-LLM llama3.2:3b"
  docker compose exec -T ollama ollama pull llama3.2:3b || true
fi

echo "Baue Gateway (zieht Whisper $WHISPER beim ersten Start)…"
WHISPER_MODEL="$WHISPER" docker compose build gateway
WHISPER_MODEL="$WHISPER" docker compose up -d gateway

echo "Warmer Whisper-Start (ein leerer Health reicht nicht – Modell kommt beim ersten /api/turn)…"
curl -sf http://127.0.0.1:8090/api/health || true
echo
curl -sf http://127.0.0.1:8090/api/options | head -c 400 || true
echo
echo "Fertig. Stimmen brauchen keinen Download (edge-tts online)."
echo "UI: http://SERVER-IP:8090/"
