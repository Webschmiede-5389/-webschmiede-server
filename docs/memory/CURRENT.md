# Aktueller Fokus

Stand: 2026-08-04

## Jetzt

**Platform Unification SCHRITT 5 MERGE (2026-08-04):** In Integrationsbranch `feature/platform-unification-branding-pilot` übernommen. Server Squash `44881c2`, CRM Merge `81398b4`. Staging gestoppt. Urteil **MERGED_NO_DEPLOY**. Kein Prod-Deploy. → `docs/platform-unification/step-5-acceptance-report.md`

**Platform Unification SCHRITT 5 (2026-08-04):** Isoliertes PostgreSQL-Staging + Playwright Browser-Drill + Visual-Baselines 390/768/1440 + Agency-Werkzeuge-E2E. Urteil **BRANDING_PILOT_READY**. Server `b8e2bf2`, CRM Worktree `4af56fc` (auf `878cc23`). Stash unangetastet. Kein Prod-Deploy. → `docs/platform-unification/step-5-acceptance-report.md`

**Platform Unification SCHRITT 4 (2026-08-02):** Suite-Isolation Fix + Evidence. CRM Full-Suite **246 passed / 0 failed / 0 errors** (venv). Staging-Browser/Visual-Baselines noch offen → Urteil weiter **NOT_READY**. Stash unangetastet. → `docs/platform-unification/step-4-*.md`


**Platform Unification SCHRITT 3 (2026-08-02):** Branding-Pilot Code fertig (CRM Login/AppShell/Dashboard + Agency Werkzeuge + `platform_registry.yaml`). Branches: Server `feature/platform-unification-branding-pilot` @ `6987fa8`, CRM gleicher Branchname @ `3276689`. Urteil **NOT_READY** (volle CRM-Suite nicht grün, Staging-E2E/Visual-Baselines offen). Kein Prod-Deploy. → `docs/platform-unification/step-3-*.md`

**Platform Unification SCHRITT 2 (2026-08-02):** Shared Design System ready — Tokens, AppShell-Lab `/design-system`, Brand-Manifest, Lint+Tests. **Keine** CRM-/Cockpit-Migration, kein Prod-Deploy. Urteil **DESIGN_SYSTEM_READY**. → `docs/platform-unification/step-2-report.md`

**Platform Unification SCHRITT 1 (2026-08-02):** Read-only Inventur + Docs unter `docs/platform-unification/`. Urteil **INVENTORY_COMPLETE**. Lead Creator = DHK Leads. → Topic `platform-unification.md`

**Nils Prospect Defaults PASS (2026-08-02):** Release `nils-entity-routing-9f90f42bdea6` live. Kein stilles DE/art6_1_f mehr. Canary ID16 country/legal NULL, outbound gesperrt, success_count=2/5. Caps unverändert isoliert. Urteil **LIMITED_PRODUCTION_PASS**. STOP. → Topic `nils-entity-routing.md`

**Login-/Hackerschutz live (2026-07-28):** Shared SQLite Rate-Limit, Admin+Agency 2FA-UI, Password-Header nur intern/Allowlist. → `docs/memory/topics/shy001-login-sicherheit.md` (2FA einmal in Authenticator bestätigen)

**SHY001 Warenkorb-Upsell live (2026-07-28):** Getränk-Hinweis im Cart/Checkout (Drehspieß→Ayran, sonst Cola), E-Mail-Upsell unverändert. → `docs/memory/topics/shy001-cart-upsell.md`

**Route-Watchdog Fix (2026-07-28):** n8n/Voice nicht mehr `127.0.0.1` auf web (False-Alarm), sondern `AUTO_HOST:5678/8090`. Dry-run web+auto OK.

**Watchdogs repariert (2026-07-28):** Nightly auf auto (fehlende .py + Akquise-Rotation-Marker), Portal-Checks auf snackhouse-yassine.de. Nightly `--check-only` → ok. WhatsApp-Token weiter offen (braucht Christian).

**SHY001 UX Follow-ups live (2026-07-28):** Live-Status-Link in Mails + Deep-Link, Auto-Texte Klartext, Vorbestell-Beep, Gutschein auf Ops-Karte, 4-Wochen-Business-Scan. → `docs/memory/topics/shy001-ux-followups.md`


**SHY001 System-Review A–F (2026-07-28):** Logo in Shop-Mails, Consent+Freq-Cap, Promo-Blast, Auto-Texte-UI, Schülerpreis+Gutschein im Submit, Reorder-Fix, Ops Tablet-Check. → `docs/memory/topics/shy001-system-review.md`


**SHY001 Schüler-Freischaltung + Vorbestellung (2026-07-28):** Admin-Suche Name/SHY-Nummer zum Freischalten. Wunschzeit klarer („Abholung um 12:30“). Betriebskarte: Schüler-Pill. → `docs/memory/topics/shy001-schueler-vorbestellung.md`

**SHY001 Aktionen/Kunden/Follow-up (2026-07-28):** Aktions-Banner oben auf Startseite + Bestellen. Kundennummer K-/SHY-. Follow-up nur E-Mail. Stempel+Schüler im Konto schon drin. → `docs/memory/topics/shy001-aktionen-kunden-followup.md`

**Loop-/Stack-Scan Agency (2026-07-28):** Kein aktiver Stack Overflow live. Landminen (Admin-Preview Hoisting, toter order-Wrap) entfernt. LLM Dispatcher Reentrancy-Guard live. Scanner: `scripts/scan_hoist_recursion_traps.py`. → `docs/memory/topics/agency-loop-scan.md`

**DHK Leads Dashboard live (2026-07-26):** `https://leads.digitalehandwerkskunst.de` — Docker auf web-01, Nginx+SSL via Certbot. Login: `admin` / Passwort in `deploy.secrets.local` (Zeile `DHK_PASS`). Deploy-Skript: `deploy_dhk_leads.py`. Projekt lokal: `projects/B2B-Kundenfänger für Digitale Handwerkskunst/`.



## Jetzt

**Verträge IP/Plattform (2026-07-24):** AGB Ziffer 5 + Auftrag § 4 live in DocuSeal (Rails-Upload). FAQ Klartext: `faq-eigentum-plattform.md`. → `docs/memory/topics/vertraege-softwareplattform.md`

**SHY001 Bestellportal UX:** Live deployed 2026-07-24 (Hotfix `shop_status`/`order_portal` nachgezogen). Shipcheck health/shop-status/bestellen OK. → `docs/memory/topics/shy001-bestellportal-ux.md`

**SHY001 Tenant-SoT (Öffnungsstatus):** Analyse + Repo-Fix `shop_status.py` / `/api/shop-status` / Order-Guard / Tests grün. Deploy noch **nicht**. Details: `docs/memory/topics/shy001-tenant-sot.md`


**Voice Browser-Assistent:** Schritt 1+2 lokal. Modelle+Bench fertig. Entscheidung: **bedingt bereit** (qwen3 Thinking-Blocker). Report `voice-agent/docs/STEP2-BENCHMARK-REPORT.md` → `docs/memory/topics/voice-browser-assistent.md`


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
