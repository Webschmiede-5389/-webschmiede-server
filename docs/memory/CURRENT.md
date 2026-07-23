# Aktueller Fokus

Stand: 2026-07-20

## Jetzt

**Telegram Agency-Hirn + Workorders:** Aufträge direkt umsetzen (Kunden-JSON) oder Cursor-Handoff.  
Dashboard `/workorders.html` · Doku `docs/agency/workorders.md`  
LLM qwen2.5:14b · Meeting-Scan · Nils/Stefan.  
**Menschlicher Ton + Companion:** `human_voice.py`, freies Plaudern, Wetter/Suche (`llm_web.py`), Sprachnachrichten via Whisper Gateway `:8090`.  
Optional ChatGPT-Niveau: `LLM_PROVIDER=cloud` + OpenAI/Grok/Gemini-Key (bezahlt, nur nach OK).  
**Speed 2026-07-19:** Kein Fake-Hintergrundjob; kürzere Tokens; Gunicorn `--timeout 120 -w 3`; Ollama `keep_alive`. PSA-Bericht an Christian nachgeholt.  
**Register-API:** OpenRegister Free live (`OPENREGISTER_API_KEY`).  
**Fokus jetzt:** Auth Phase 1+2 live (Agency Session, Users, Reset, TOTP-API). YubiKey noch offen.  
Nils Dispatcher + Requesty-Primary **live** (Key in `requesty.secrets.local`, Modell `openai/gpt-4o-mini`, Server-Smoke OK).  
**Requesty EU-Engine live:** Gateway `router.eu.requesty.ai`, EU-Modellketten A/B/C, Telegram-Streaming.  
**Speed-Fix v2:** Messung: LLM ~0,4s. Bremse war Telegram-Streaming + Budget-API. Jetzt Direktpfad `send_fast_llm` (1 Call, 1 Nachricht), Stream aus, Budget-Netzwerk nur bei Bildern.  
**Telegram Flood-Fix (2026-07-20):** Ursache war Webhook-Timeout → Telegram-Retries → mehrfach gleiche Antwort. Fix: Dedup `update_id`, Chat-Lock, Webhook ACK sofort + Background-Thread, keine Zwischennachrichten.  
**Telegram Krisenfest v3 (2026-07-20):** In-Memory Dedup 60s + SQLite, Thread-Pool, Session pro `chat_id` (nur user/assistant), 429-Retry, höfliche Soft-Errors, Voice mit `record_voice`+STT im Worker nach ACK, Anti-Rollen-Halluzination im System-Prompt.  
**Silence-Bug Fix:** `app._get_current_object()` crashte den Webhook (500). Nach Claim keine Verarbeitung → tot. Fix: `app.app_context()` + nie 500 an Telegram. Stuck Claims geleert, Webhook neu gesetzt.  
**Kostenfalle-Schutz:** Bilder erst nach Kostenvoranschlag + „ja“ (`NILS_PAID_MEDIA_CONFIRM=1`). Soft-Limits $8/Tag $20/Monat, max 5 Bilder/Tag. Telegram `budget`. Chat billig-zuerst.  
**Antwortlänge:** Telegram war absichtlich auf ~280 Tokens + „unter 8 Sätzen“ gedrosselt (Speed). Jetzt ~900 Tokens + substanzielle Antworten bei Ideen/Analyse.  
**Voice-UX:** Kein „(verstanden: …)“-Vorspann mehr. Bei Sprachnachricht: Hörfehler höflich korrigieren („Meinst du eher …?“), dann normal frei antworten.  
**Inventar live (2026-07-20):** Nils kennt seinen Werkzeugkasten live (`nils_inventory.py`), entscheidet selbst, greift zu. Prompt in jedem Chat + Auto-Reach bei Research. Telegram: `inventar` / `was hast du`. Christian nennt den Auftrag, nicht die Tools.  
**Cursor Auto-Deploy:** nach Freigabe → Agent → Pull/Sync Live (braucht `GITHUB_TOKEN` – noch leer).  
**Tagesreport:** Cron morgens Telegram/Mail · `tagesreport`.  
**Kosten-Wächter:** Buyer stoppen, Akquise-Nacht pausiert bis OK · `kostenwächter` / `budget`.  
**Discovery vor Bau:** Rückfragen + Vorschläge, dann „mach das“.  
**ETA + Job-Watchdog:** keine Fake-Minuten, Overdue-Ping.  
**Hirn-Wächter / Night-Worker:** alle 20 Min + Nacht-Digest · `hirnwächter`.  
**UX- + Fact-Gate:** Pflicht vor „fertig/live“ (Links, Mobile, Flow) · `ux check` · Rule `ux-ship-gate.mdc`.  
**Guided Cursor-Level:** verstehen → Fragen → Vorschläge → Freigabe → erst dann Aktion (`nils_guided.py`).  
**Orchestrator** + Truth + Deep Research. Chat humanisiert. Cursor-Bridge OK.

**Sales-Pipeline + Funnel-Begleiter:** Invite → Discovery → Pain-Angebot → Preis → Stripe.  
Pings an Christian (Mail/WhatsApp/Telegram) + Reminder-Cron alle 4h.  
Dashboard `/sales-dashboard.html` · Doku `docs/agency/sales-pipeline.md`

**Buchhaltungs-Onboarding-Wizard live:** `/buchhaltung-onboarding.html`  
Tools → Fragen → Angebot → AVV → Vault. Doku `docs/agency/buchhaltung-onboarding.md`

**Ops-Guardian (Alleskönner ehrlich):** alle 15 Min Surfaces/SSL/Dual/Resource, Safe-Fix snack-api, Mail bei Gelb/Rot.  
CLI `scripts/ops_guardian_cli.py`, API `/api/nils/guardian`, Doku `docs/agency/ops-guardian.md`

**Freigabe-Check (WF15 / Shipcheck):** Links/Dashboards vor Christian HTTP-smoken.  
CLI `scripts/shipcheck_cli.py`, API `/api/agency/shipcheck`, Rule `shipcheck.mdc`.  
Nur bei `ship=true` Links nennen. Doku `docs/agency/shipcheck.md`

**Radar (WF14) live + Freitag-Cron:** n8n 07:00, web-Backup 07:05.  
Wochenreport + Install-Queue, kein Auto-Install. Doku `docs/agency/trend-scout.md`

## Offen (braucht Christian)

- **WhatsApp Nils-Ops:** Token + Phone Number ID + OWNER_PHONE (siehe `docs/agency/whatsapp-go-live.md`)
- Hetzner AVV in Console laden und ablegen
- Vor Großkunde: echter Anwalt (`ANWALT-BRIEFING.md`)
- Optional: echte Vertrags-Unterschrift-PNG
- DocuSeal SMTP Auth einmal in UI testen
- Domain SHY001 IONOS + NS Cloudflare
- Twilio DE, Umami, Tankerkoenig, INWX (nur bei Bedarf)

## Bereits erledigt ohne Christian

- Verträge CI + Kundenpaket-Send-Flow
- Messaging-Status-Check + Go-Live-Doku
- n8n WhatsApp-Outbound-Skizze (inaktiv)
- B2B-Stufen + Agentur-Vergleich

## Kostenfallen

- Hetzner-Buyer-Cron abgeschaltet
- Jay Limits live
- DocuSeal Template-API = Pro (wir nutzen Rails/Community)
- Keine Meta/Twilio-Käufe ohne OK
