# Voice Demo – eigener Stack (ohne Retell)

## Wichtig

Der aktuelle Shop-Server (`167.233.211.170`) hat nur **1–2 GB RAM**.  
Dort den Voice-Stack **nicht** starten (Portal würde leiden).

Alles für die Auswahl ist schon vorbereitet (Stimmen, Stile, Dialekte, Branchen).  
Modelle (Whisper/Ollama) laden erst auf dem **8-GB+-Server**.

## Was du in der Demo wählen kannst

### Stimmen (10, Mann/Frau)

| ID | Name | Geschlecht | Region | Typ |
|----|------|------------|--------|-----|
| conrad | Conrad | Mann | DE | ruhig, klar |
| killian | Killian | Mann | DE | jung, frisch |
| florian | Florian | Mann | DE | multilingual |
| jonas | Jonas | Mann | AT | österreichisch |
| jan | Jan | Mann | CH | schweizerisch |
| katja | Katja | Frau | DE | warm, professionell |
| amala | Amala | Frau | DE | freundlich, hell |
| seraphina | Seraphina | Frau | DE | multilingual |
| ingrid | Ingrid | Frau | AT | österreichisch |
| leni | Leni | Frau | CH | schweizerisch |

Button **Anhören** in der UI = Vorschau ohne Mikrofon.  
Stimmen kommen live von Microsoft Edge neural (kein Extra-Download).

### Sprachstile / Dialekte (9)

| ID | Stil |
|----|------|
| sachlich | Hochdeutsch, ruhig |
| freundlich | Hochdeutsch, warm |
| rheinland | leichter Rheinland-Touch |
| koelsch | Kölsch |
| platt | Plattdeutsch |
| bayrisch | Bayrisch |
| berlinerisch | Berlinerisch |
| oesterreichisch | Österreichisch |
| schweizerdeutsch | Schweizerdeutsch (leicht) |

**Ehrlich gesagt:** Die Stimme spricht weiter neural-Hochdeutsch.  
Der Dialekt steckt im **Text** (LLM). Echte Kölsch-/Platt-Aussprache gibt es bei edge-tts nicht.  
Für Produktion später: Retell-Clone oder eigenes Voice-Cloning auf dem Voice-Server.

### Akzente verstehen

Whisper bekommt je Stil einen Dialekt-Hinweis (`initial_prompt`) und VAD.  
Standard-Modell auf dem großen Server: `base` (besser als `tiny`).  
Optional: `WHISPER_MODEL=small` (braucht mehr RAM).

### Branchen

`general` · `gastro` · `handwerk` (Ordner `packs/`)

## Empfohlener Server

| | Minimum | Besser |
|--|---------|--------|
| Typ | CX32 / CX33 (4 vCPU, 8 GB) | 16 GB |
| OS | Ubuntu 24.04 | Ubuntu 24.04 |

## Installation (auf dem NEUEN Server) – nur installieren, nicht starten

```bash
cd /root/app
bash scripts/install_voice_demo.sh
```

Das Skript pullt Images, baut das Gateway, lädt Ollama- + Whisper-Modell und macht danach `docker compose down`.  
Nichts bleibt laufend. Marker: `infra/voice-demo/.install-complete`

Von Windows aus (nach Eintrag `VOICE_HOST` / `AUTO_HOST` / `WEB_HOST` in `deploy.secrets.local`):

```bash
python scripts/remote_install_voice_demo.py
```

Später starten:

```bash
cd /root/app/infra/voice-demo
docker compose up -d
```

Optional größeres Modell beim Install:

```bash
OLLAMA_MODEL=llama3.2:3b WHISPER_MODEL=small bash scripts/install_voice_demo.sh
PULL_EXTRA=1 bash scripts/install_voice_demo.sh
```

UI (erst nach Start): `http://VOICE-SERVER-IP:8090/`

## Produktregel

- **Demo / Akquise:** dieser Stack  
- **Zahlende Kunden:** Retell (`docs/agency/voice-agents.md`)

## Befehle

```bash
cd /root/app/infra/voice-demo
docker compose ps
docker compose logs -f gateway
docker compose down
```
