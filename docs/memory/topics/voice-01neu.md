# Topic: Voice-01neu Server

Stand: 2026-07-17

## Server

| | |
|--|--|
| IP | `167.233.150.230` |
| Hetzner | Voice01neu / cx43-de-2-nbg1 |
| OS | Ubuntu 24.04.4 LTS |
| Rescue | aus (Rebuild via API) |

## Secrets

`deploy.secrets.local`: `VOICE_HOST`, `VOICE_PASSWORD` (Rescue-PW aus Chat gilt nicht mehr)

## Basis installiert

Python 3.12, git, ufw (22/80/443), fail2ban, Hostname `Voice-01neu`

## Voice-Demo (2026-07-17)

- Stack: `infra/voice-demo` (Ollama + Whisper + Gateway :8090)
- Install-Marker: `/root/app/infra/voice-demo/.install-complete`
- Container laufen: `voice-demo-ollama-1`, `voice-demo-gateway-1`
- Nginx web-01: `/voice-demo/` → `167.233.150.230:8090` (alt: `62.238.43.128`)
- Smoke: `https://digitalehandwerkskunst.de/voice-demo/api/health` → 200

## Alt voice-01

`62.238.43.128` — noch nicht abgeschaltet; nach kurzem Parallelbetrieb stoppen.
