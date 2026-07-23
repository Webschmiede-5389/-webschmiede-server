"""Agency: deploy.secrets.local auf dem Server lesen/schreiben (Whitelist)."""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

# Nur diese Keys dürfen über die Web-UI gesetzt werden (kein SERVER_PASSWORD!)
KEY_CATALOG: list[dict] = [
    # ── E-Mail (IONOS / Domain) ───────────────────────────────────────────────
    {
        "id": "smtp_host",
        "key": "AGENCY_SMTP_HOST",
        "label": "SMTP Server",
        "hint": "IONOS: smtp.ionos.de · Zoho: smtp.zoho.eu",
        "group": "E-Mail (IONOS / Domain)",
        "placeholder": "smtp.ionos.de",
        "input": "text",
        "preset_ionos": "smtp.ionos.de",
    },
    {
        "id": "smtp_port",
        "key": "AGENCY_SMTP_PORT",
        "label": "SMTP Port",
        "hint": "Meist 587 (STARTTLS)",
        "group": "E-Mail (IONOS / Domain)",
        "placeholder": "587",
        "input": "text",
        "preset_ionos": "587",
    },
    {
        "id": "smtp_user",
        "key": "AGENCY_SMTP_USER",
        "label": "E-Mail-Adresse (Login)",
        "hint": "Vollständige Adresse, z. B. info@digitalehandwerkskunst.de",
        "group": "E-Mail (IONOS / Domain)",
        "placeholder": "info@digitalehandwerkskunst.de",
        "input": "email",
    },
    {
        "id": "smtp_pass",
        "key": "AGENCY_SMTP_PASS",
        "label": "E-Mail-Passwort",
        "hint": "Postfach-Passwort aus IONOS (nicht IONOS-Kundenlogin)",
        "group": "E-Mail (IONOS / Domain)",
        "placeholder": "••••••••",
        "input": "password",
    },
    {
        "id": "smtp_from",
        "key": "AGENCY_SMTP_FROM",
        "label": "Absender-Anzeige",
        "hint": "z. B. Webschmiede <info@digitalehandwerkskunst.de>",
        "group": "E-Mail (IONOS / Domain)",
        "placeholder": "Webschmiede <info@digitalehandwerkskunst.de>",
        "input": "text",
    },
    {
        "id": "reply_to",
        "key": "AGENCY_REPLY_TO",
        "label": "Antwort-Adresse",
        "hint": "Wohin Kunden antworten",
        "group": "E-Mail (IONOS / Domain)",
        "placeholder": "info@digitalehandwerkskunst.de",
        "input": "email",
    },
    {
        "id": "owner_email",
        "key": "AGENCY_OWNER_EMAIL",
        "label": "Deine E-Mail (Agency)",
        "hint": "Für Test-Mails und Support-Footer",
        "group": "E-Mail (IONOS / Domain)",
        "placeholder": "christian@…",
        "input": "email",
    },
    # ── Abrechnung ────────────────────────────────────────────────────────────
    {
        "id": "stripe_secret",
        "key": "STRIPE_SECRET_KEY",
        "label": "Stripe Secret Key",
        "hint": "sk_test_… oder sk_live_… · Developers → API keys",
        "group": "Abrechnung (Stripe)",
        "placeholder": "sk_…",
        "input": "password",
    },
    {
        "id": "stripe_webhook",
        "key": "STRIPE_WEBHOOK_SECRET",
        "label": "Stripe Webhook Secret",
        "hint": "whsec_… · Endpoint: https://digitalehandwerkskunst.de/api/stripe/webhook",
        "group": "Abrechnung (Stripe)",
        "placeholder": "whsec_…",
        "input": "password",
    },
    # ── Akquise ───────────────────────────────────────────────────────────────
    {
        "id": "google_places",
        "key": "GOOGLE_PLACES_API_KEY",
        "label": "Google Places API",
        "hint": "Projekt „Webschmiede Akquise“ · Places API aktivieren",
        "group": "Akquise Engine",
        "placeholder": "AIza…",
        "input": "password",
    },
    {
        "id": "meta_ads",
        "key": "META_AD_LIBRARY_TOKEN",
        "label": "Meta Ad Library (optional)",
        "hint": "Meta Developer Token mit ads_read",
        "group": "Akquise Engine",
        "placeholder": "EAA…",
        "input": "password",
    },
    {
        "id": "northdata",
        "key": "NORTHDATA_API_KEY",
        "label": "North Data API (optional, teuer)",
        "hint": "Ab ~500 €/Monat · nur bei Bedarf. Alltag: OpenRegister Free.",
        "group": "Akquise Engine",
        "placeholder": "nd_…",
        "input": "password",
    },
    {
        "id": "openregister",
        "key": "OPENREGISTER_API_KEY",
        "label": "OpenRegister API (empfohlen)",
        "hint": "Handelsregister DE · Free 500 Credits/Monat · openregister.de",
        "group": "Akquise Engine",
        "placeholder": "…",
        "input": "password",
    },
    {
        "id": "firecrawl",
        "key": "FIRECRAWL_API_KEY",
        "label": "Firecrawl API (optional)",
        "hint": "Website-Scrape für Nils Research · sonst lokaler Crawl",
        "group": "Akquise Engine",
        "placeholder": "fc-…",
        "input": "password",
    },
    # ── Domains (IONOS Hosting API — DNS Agentur-Domain) ──────────────────────
    {
        "id": "ionos_api_prefix",
        "key": "IONOS_API_PREFIX",
        "label": "IONOS API Präfix",
        "hint": "developer.hosting.ionos.de → API Keys · öffentlicher Teil",
        "group": "Domains (IONOS)",
        "placeholder": "z. B. 014a5873…",
        "input": "text",
    },
    {
        "id": "ionos_api_secret",
        "key": "IONOS_API_SECRET",
        "label": "IONOS API Secret / Verschlüsselung",
        "hint": "Nur einmal angezeigt · nie im Chat teilen · Header = Präfix.Secret",
        "group": "Domains (IONOS)",
        "placeholder": "••••••••",
        "input": "password",
    },
    # ── Domains (INWX — Kauf .de + DNS) ───────────────────────────────────────
    {
        "id": "inwx_user",
        "key": "INWX_USER",
        "label": "INWX Benutzer",
        "hint": "inwx.de Login · Domains + DNS API",
        "group": "Domains (INWX)",
        "placeholder": "dein-user",
        "input": "text",
    },
    {
        "id": "inwx_password",
        "key": "INWX_PASSWORD",
        "label": "INWX Passwort / API-Passwort",
        "hint": "Account → API / Passwort · nicht im Chat teilen",
        "group": "Domains (INWX)",
        "placeholder": "••••••••",
        "input": "password",
    },
    {
        "id": "inwx_contact",
        "key": "INWX_CONTACT_ID",
        "label": "INWX Kontakt-ID",
        "hint": "Kontakte → Handle-Nummer für Registrant (eine Zahl)",
        "group": "Domains (INWX)",
        "placeholder": "12345678",
        "input": "text",
    },
    # ── Domains (Cloudflare, optional) ────────────────────────────────────────
    {
        "id": "cloudflare_token",
        "key": "CLOUDFLARE_API_TOKEN",
        "label": "Cloudflare API Token (optional)",
        "hint": "Nur falls noch Cloudflare-DNS genutzt wird",
        "group": "Domains (Cloudflare)",
        "placeholder": "cfut_…",
        "input": "password",
    },
    {
        "id": "cloudflare_account",
        "key": "CLOUDFLARE_ACCOUNT_ID",
        "label": "Cloudflare Account ID (optional)",
        "hint": "Rechts im Cloudflare-Dashboard",
        "group": "Domains (Cloudflare)",
        "placeholder": "32 Zeichen Hex",
        "input": "text",
    },
    {
        "id": "tankerkoenig",
        "key": "TANKERKOENIG_API_KEY",
        "label": "Tankerkoenig API Key (TourMeter Sprit)",
        "hint": "kostenlos: creativecommons.tankerkoenig.de · Diesel/Benzin für TourMeter",
        "group": "TourMeter",
        "placeholder": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        "input": "password",
    },
    # ── Voice (Retell) ────────────────────────────────────────────────────────
    {
        "id": "retell_api",
        "key": "RETELL_API_KEY",
        "label": "Retell API Key",
        "hint": "Retell Dashboard → Settings → API Keys · Voice Agent für Kunden",
        "group": "Voice (Retell)",
        "placeholder": "key_…",
        "input": "password",
    },
    # ── Voice Telefonie (Twilio → Retell SIP) ─────────────────────────────────
    {
        "id": "twilio_account_sid",
        "key": "TWILIO_ACCOUNT_SID",
        "label": "Twilio Account SID",
        "hint": "twilio.com Console → Account SID (AC…)",
        "group": "Voice Telefonie (Twilio)",
        "placeholder": "AC…",
        "input": "password",
    },
    {
        "id": "twilio_auth_token",
        "key": "TWILIO_AUTH_TOKEN",
        "label": "Twilio Auth Token",
        "hint": "Console → Auth Token · Doku: docs/agency/twilio-retell-setup.md",
        "group": "Voice Telefonie (Twilio)",
        "placeholder": "…",
        "input": "password",
    },
    {
        "id": "twilio_voice_number",
        "key": "TWILIO_VOICE_NUMBER",
        "label": "Twilio Voice-Nummer",
        "hint": "E.164, z. B. +492251… (DE Ortsnummer für Retell)",
        "group": "Voice Telefonie (Twilio)",
        "placeholder": "+49…",
        "input": "text",
    },
    {
        "id": "twilio_sip_termination_uri",
        "key": "TWILIO_SIP_TERMINATION_URI",
        "label": "Twilio SIP Termination URI",
        "hint": "Nach Elastic SIP Trunk · für Retell Import",
        "group": "Voice Telefonie (Twilio)",
        "placeholder": "webschmiede.pstn.twilio.com",
        "input": "text",
    },
    # ── DocuSeal (Angebote unterschreiben) ───────────────────────────────────
    {
        "id": "docuseal_url",
        "key": "DOCUSEAL_URL",
        "label": "DocuSeal Basis-URL",
        "hint": "Self-host: https://sign.digitalehandwerkskunst.de · Cloud: https://api.docuseal.com",
        "group": "DocuSeal (Signatur)",
        "placeholder": "https://sign.digitalehandwerkskunst.de",
        "input": "text",
        "preset_if_empty": "https://sign.digitalehandwerkskunst.de",
    },
    {
        "id": "docuseal_api_token",
        "key": "DOCUSEAL_API_TOKEN",
        "label": "DocuSeal X-Auth-Token",
        "hint": "Self-host: /settings/api · Cloud: console.docuseal.com/api",
        "group": "DocuSeal (Signatur)",
        "placeholder": "…",
        "input": "password",
    },
    # ── Cal.com (Terminbuchung) ───────────────────────────────────────────────
    {
        "id": "calcom_url",
        "key": "CALCOM_URL",
        "label": "Cal.com Basis-URL",
        "hint": "Self-host: https://cal.digitalehandwerkskunst.de",
        "group": "Cal.com (Termine)",
        "placeholder": "https://cal.digitalehandwerkskunst.de",
        "input": "text",
        "preset_if_empty": "https://cal.digitalehandwerkskunst.de",
    },
    {
        "id": "calcom_api_key",
        "key": "CALCOM_API_KEY",
        "label": "Cal.com API Key",
        "hint": "Cal.com → Settings → Developer → API Keys · Format oft cal_live_… · Nie im Chat posten",
        "group": "Cal.com (Termine)",
        "placeholder": "cal_live_…",
        "input": "password",
    },
    {
        "id": "llm_provider",
        "key": "LLM_PROVIDER",
        "label": "LLM Provider",
        "hint": "auto = Ollama gratis zuerst · cloud = Grok/OpenAI/Gemini zuerst · oder ollama/openai/grok/gemini",
        "group": "KI (Nils / Jarvis)",
        "placeholder": "auto",
        "input": "text",
        "preset_if_empty": "auto",
    },
    {
        "id": "ollama_url",
        "key": "OLLAMA_URL",
        "label": "Ollama URL",
        "hint": "Standard: http://AUTO_HOST:11434 · Voice-Demo Ollama auf auto-01",
        "group": "KI (Nils / Jarvis)",
        "placeholder": "http://…:11434",
        "input": "text",
    },
    {
        "id": "ollama_model",
        "key": "OLLAMA_MODEL",
        "label": "Ollama Modell",
        "hint": "Live: qwen2.5:14b auf auto-01 · Fallback llama3.2:1b",
        "group": "KI (Nils / Jarvis)",
        "placeholder": "qwen2.5:14b",
        "input": "text",
        "preset_if_empty": "qwen2.5:14b",
    },
    {
        "id": "primary_llm_gateway",
        "key": "PRIMARY_LLM_GATEWAY",
        "label": "Primary LLM Gateway URL",
        "hint": "z. B. https://router.requesty.ai/v1 · OpenAI-kompatibel · Bezahlt, nur nach OK",
        "group": "KI (Nils / Jarvis)",
        "placeholder": "https://router.requesty.ai/v1",
        "input": "text",
        "preset_if_empty": "https://router.requesty.ai/v1",
    },
    {
        "id": "primary_api_key",
        "key": "PRIMARY_API_KEY",
        "label": "Primary Gateway API Key",
        "hint": "Requesty / EU-Smart-Router Key · Nie im Chat posten · Nur nach OK",
        "group": "KI (Nils / Jarvis)",
        "placeholder": "req_…",
        "input": "password",
    },
    {
        "id": "fallback_openai_gateway",
        "key": "FALLBACK_OPENAI_GATEWAY",
        "label": "Fallback OpenAI Gateway",
        "hint": "Notfall Direkt-OpenAI · Standard https://api.openai.com/v1",
        "group": "KI (Nils / Jarvis)",
        "placeholder": "https://api.openai.com/v1",
        "input": "text",
        "preset_if_empty": "https://api.openai.com/v1",
    },
    {
        "id": "fallback_openai_key",
        "key": "FALLBACK_OPENAI_KEY",
        "label": "Fallback OpenAI Key",
        "hint": "sk-… · Alias zu OPENAI_API_KEY · Nur nach OK",
        "group": "KI (Nils / Jarvis)",
        "placeholder": "sk-…",
        "input": "password",
    },
    {
        "id": "openrouter_api_key",
        "key": "OPENROUTER_API_KEY",
        "label": "OpenRouter API Key (optional)",
        "hint": "Zweites Gateway · optional neben Requesty · Nur nach OK",
        "group": "KI (Nils / Jarvis)",
        "placeholder": "sk-or-…",
        "input": "password",
    },
    {
        "id": "nils_dispatcher",
        "key": "NILS_DISPATCHER",
        "label": "Nils Dispatcher",
        "hint": "1 = Smart-Router A/B/C an · 0 = nur klassischer Provider-Fallback",
        "group": "KI (Nils / Jarvis)",
        "placeholder": "1",
        "input": "text",
        "preset_if_empty": "1",
    },
    {
        "id": "openai_api_key",
        "key": "OPENAI_API_KEY",
        "label": "OpenAI API Key (optional Backup)",
        "hint": "Gleichwertig zu FALLBACK_OPENAI_KEY · sonst leer lassen",
        "group": "KI (Nils / Jarvis)",
        "placeholder": "sk-…",
        "input": "password",
    },
    {
        "id": "openai_model",
        "key": "OPENAI_MODEL",
        "label": "OpenAI Modell (optional)",
        "hint": "Standard gpt-4o-mini",
        "group": "KI (Nils / Jarvis)",
        "placeholder": "gpt-4o-mini",
        "input": "text",
        "preset_if_empty": "gpt-4o-mini",
    },
    {
        "id": "xai_api_key",
        "key": "XAI_API_KEY",
        "label": "Grok / xAI API Key (optional)",
        "hint": "Bezahlt · console.x.ai · Nur nach OK. LLM_PROVIDER=cloud oder grok",
        "group": "KI (Nils / Jarvis)",
        "placeholder": "xai-…",
        "input": "password",
    },
    {
        "id": "xai_model",
        "key": "XAI_MODEL",
        "label": "Grok Modell (optional)",
        "hint": "z. B. grok-2-latest",
        "group": "KI (Nils / Jarvis)",
        "placeholder": "grok-2-latest",
        "input": "text",
        "preset_if_empty": "grok-2-latest",
    },
    {
        "id": "gemini_api_key",
        "key": "GEMINI_API_KEY",
        "label": "Gemini API Key (optional)",
        "hint": "Bezahlt · Google AI Studio · LLM_PROVIDER=cloud oder gemini",
        "group": "KI (Nils / Jarvis)",
        "placeholder": "AIza…",
        "input": "password",
    },
    {
        "id": "gemini_model",
        "key": "GEMINI_MODEL",
        "label": "Gemini Modell (optional)",
        "hint": "Standard gemini-2.0-flash",
        "group": "KI (Nils / Jarvis)",
        "placeholder": "gemini-2.0-flash",
        "input": "text",
        "preset_if_empty": "gemini-2.0-flash",
    },
    {
        "id": "voice_gateway_url",
        "key": "VOICE_GATEWAY_URL",
        "label": "Voice-Gateway URL (STT)",
        "hint": "Whisper auf auto-01, Standard http://AUTO_HOST:8090",
        "group": "KI (Nils / Jarvis)",
        "placeholder": "http://…:8090",
        "input": "text",
    },
    # ── Messaging (GHL-Ersatz: SMS + WhatsApp) ───────────────────────────────
    {
        "id": "sms_enabled",
        "key": "SMS_ENABLED",
        "label": "SMS aktiv",
        "hint": "true oder false",
        "group": "Messaging (SMS + WhatsApp)",
        "placeholder": "true",
        "input": "text",
    },
    {
        "id": "sms_api_key",
        "key": "SMS_API_KEY",
        "label": "seven.io API-Key",
        "hint": "https://app.seven.io → Developer → API-Key",
        "group": "Messaging (SMS + WhatsApp)",
        "placeholder": "…",
        "input": "password",
    },
    {
        "id": "sms_sender",
        "key": "SMS_SENDER",
        "label": "SMS-Absender",
        "hint": "Max. 11 Zeichen, z. B. Webschmiede oder Shop-Name",
        "group": "Messaging (SMS + WhatsApp)",
        "placeholder": "Webschmiede",
        "input": "text",
    },
    {
        "id": "owner_phone",
        "key": "OWNER_PHONE",
        "label": "Inhaber-Handy (Tests + Nils-WA)",
        "hint": "Deine Privatnummer +49… · WhatsApp an Business = Nils-Ops",
        "group": "Messaging (SMS + WhatsApp)",
        "placeholder": "+49177…",
        "input": "text",
    },
    {
        "id": "nils_ops_owners",
        "key": "NILS_OPS_OWNER_PHONES",
        "label": "Nils WhatsApp Owner-Whitelist",
        "hint": "Optional mehrere Nummern, Komma-getrennt. Sonst reicht OWNER_PHONE.",
        "group": "Messaging (SMS + WhatsApp)",
        "placeholder": "+49177…,+49176…",
        "input": "text",
    },
    {
        "id": "wa_token",
        "key": "WHATSAPP_ACCESS_TOKEN",
        "label": "WhatsApp Access Token (Meta)",
        "hint": "Meta Developers → App → WhatsApp → API Setup · dauerhaft System-User Token",
        "group": "Messaging (SMS + WhatsApp)",
        "placeholder": "EAAG…",
        "input": "password",
    },
    {
        "id": "wa_phone_id",
        "key": "WHATSAPP_PHONE_NUMBER_ID",
        "label": "WhatsApp Phone Number ID",
        "hint": "Meta → WhatsApp → API Setup · Phone number ID (nicht die +49-Nummer)",
        "group": "Messaging (SMS + WhatsApp)",
        "placeholder": "1234567890",
        "input": "text",
    },
    {
        "id": "wa_verify",
        "key": "WHATSAPP_VERIFY_TOKEN",
        "label": "WhatsApp Webhook Verify-Token",
        "hint": "Beliebiges Geheimnis, das du in Meta beim Webhook einträgst",
        "group": "Messaging (SMS + WhatsApp)",
        "placeholder": "webschmiede-verify",
        "input": "password",
    },
    {
        "id": "wa_display",
        "key": "WHATSAPP_DISPLAY_PHONE",
        "label": "WhatsApp Anzeige-Nummer",
        "hint": "Die +49-Nummer, die Kunden sehen (optional, Doku)",
        "group": "Messaging (SMS + WhatsApp)",
        "placeholder": "+49…",
        "input": "text",
    },
    {
        "id": "wa_waba",
        "key": "WHATSAPP_BUSINESS_ACCOUNT_ID",
        "label": "WhatsApp Business Account ID",
        "hint": "Optional · WABA-ID aus Meta Business",
        "group": "Messaging (SMS + WhatsApp)",
        "placeholder": "…",
        "input": "text",
    },
    {
        "id": "meta_app_id",
        "key": "META_APP_ID",
        "label": "Meta App ID",
        "hint": "developers.facebook.com → App · für Embedded Signup + Webhook-Signatur",
        "group": "Messaging (SMS + WhatsApp)",
        "placeholder": "1234567890",
        "input": "text",
    },
    {
        "id": "meta_app_secret",
        "key": "META_APP_SECRET",
        "label": "Meta App Secret",
        "hint": "App-Einstellungen → Basis · für OAuth + X-Hub-Signature-256",
        "group": "Messaging (SMS + WhatsApp)",
        "placeholder": "••••••••",
        "input": "password",
    },
    {
        "id": "meta_embedded_config",
        "key": "META_EMBEDDED_CONFIG_ID",
        "label": "Meta Embedded Signup Config ID",
        "hint": "Optional · WhatsApp → Embedded Signup in Meta Developers",
        "group": "Messaging (SMS + WhatsApp)",
        "placeholder": "…",
        "input": "text",
    },
    {
        "id": "tg_token",
        "key": "TELEGRAM_BOT_TOKEN",
        "label": "Telegram Bot Token (Nils Ops)",
        "hint": "@BotFather → /newbot · intern Christian↔Nils, nicht Kundenkanal",
        "group": "Messaging (Telegram Ops)",
        "placeholder": "7123456789:AAH…",
        "input": "password",
    },
    {
        "id": "tg_owner",
        "key": "TELEGRAM_OWNER_CHAT_ID",
        "label": "Telegram Owner Chat-ID",
        "hint": "Bot /start schreiben → Chat-ID kommt zurück · optional mehrere als TELEGRAM_OWNER_CHAT_IDS",
        "group": "Messaging (Telegram Ops)",
        "placeholder": "123456789",
        "input": "text",
    },
    {
        "id": "tg_webhook_secret",
        "key": "TELEGRAM_WEBHOOK_SECRET",
        "label": "Telegram Webhook Secret (optional)",
        "hint": "Beliebiges Geheimnis · Header X-Telegram-Bot-Api-Secret-Token",
        "group": "Messaging (Telegram Ops)",
        "placeholder": "webschmiede-tg-secret",
        "input": "password",
    },
    # ── Server (Hetzner Cloud) ────────────────────────────────────────────────
    {
        "id": "hetzner_api",
        "key": "HETZNER_API_TOKEN",
        "label": "Hetzner Cloud API Token",
        "hint": "console.hetzner.cloud → Security → API Tokens · Read & Write",
        "group": "Server (Hetzner Cloud)",
        "placeholder": "Token…",
        "input": "password",
    },
    # ── Off-Server Backup (SFTP / Hetzner Storage Box) ───────────────────────
    {
        "id": "backup_sftp_host",
        "key": "BACKUP_SFTP_HOST",
        "label": "Backup SFTP Host",
        "hint": "Hetzner Storage Box: u123456.your-storagebox.de",
        "group": "Backup (Off-Server)",
        "placeholder": "u123456.your-storagebox.de",
        "input": "text",
    },
    {
        "id": "backup_sftp_user",
        "key": "BACKUP_SFTP_USER",
        "label": "Backup SFTP User",
        "hint": "Storage Box Benutzername (u123456)",
        "group": "Backup (Off-Server)",
        "placeholder": "u123456",
        "input": "text",
    },
    {
        "id": "backup_sftp_pass",
        "key": "BACKUP_SFTP_PASS",
        "label": "Backup SFTP Passwort",
        "hint": "Storage Box Passwort · Ordner backups/ anlegen",
        "group": "Backup (Off-Server)",
        "placeholder": "••••••••",
        "input": "password",
    },
    {
        "id": "backup_sftp_path",
        "key": "BACKUP_SFTP_PATH",
        "label": "Remote-Ordner",
        "hint": "Relativer Pfad auf der Storage Box, z. B. backups",
        "group": "Backup (Off-Server)",
        "placeholder": "backups",
        "input": "text",
    },
    # ── Agency Admin ──────────────────────────────────────────────────────────
    {
        "id": "agency_admin_pw",
        "key": "AGENCY_ADMIN_PASSWORD",
        "label": "Agency Admin-Passwort",
        "hint": "Login für /agency und dieses Portal",
        "group": "Agency Zugang",
        "placeholder": "Neues Passwort…",
        "input": "password",
    },
]

ALLOWED_KEYS = {item["key"] for item in KEY_CATALOG}
ENV_SYNC_KEYS = (
    "AGENCY_ADMIN_PASSWORD",
    "AGENCY_OWNER_EMAIL",
    "RETELL_API_KEY",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_VOICE_NUMBER",
    "TWILIO_SIP_TERMINATION_URI",
    "DOCUSEAL_URL",
    "DOCUSEAL_API_TOKEN",
    "CALCOM_URL",
    "CALCOM_API_KEY",
    "LLM_PROVIDER",
    "OLLAMA_URL",
    "OLLAMA_MODEL",
    "OPENROUTER_API_KEY",
    "PRIMARY_LLM_GATEWAY",
    "PRIMARY_API_KEY",
    "PRIMARY_LLM_MODEL",
    "FALLBACK_OPENAI_GATEWAY",
    "FALLBACK_OPENAI_KEY",
    "NILS_DISPATCHER",
    "NILS_STRIP_PII",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "XAI_API_KEY",
    "XAI_MODEL",
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "VOICE_GATEWAY_URL",
    "SMS_ENABLED",
    "SMS_API_KEY",
    "SMS_SENDER",
    "OWNER_PHONE",
    "NILS_OPS_OWNER_PHONES",
    "WHATSAPP_ACCESS_TOKEN",
    "WHATSAPP_PHONE_NUMBER_ID",
    "WHATSAPP_VERIFY_TOKEN",
    "WHATSAPP_DISPLAY_PHONE",
    "WHATSAPP_BUSINESS_ACCOUNT_ID",
    "META_APP_ID",
    "META_APP_SECRET",
    "META_EMBEDDED_CONFIG_ID",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_OWNER_CHAT_ID",
    "TELEGRAM_OWNER_CHAT_IDS",
    "TELEGRAM_WEBHOOK_SECRET",
)
BACKEND_ENV = Path("/root/app/backend/.env")


def secrets_path() -> Path:
    env = os.getenv("DEPLOY_SECRETS_PATH", "").strip()
    if env:
        return Path(env)
    server = Path("/root/app/deploy.secrets.local")
    if server.parent.exists():
        return server
    return Path(__file__).resolve().parents[2] / "deploy.secrets.local"


def _parse_file(path: Path) -> tuple[list[str], dict[str, str]]:
    if not path.exists():
        return [], {}
    lines = path.read_text(encoding="utf-8").splitlines()
    values: dict[str, str] = {}
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = line.split("=", 1)
        values[k.strip()] = v.strip()
    return lines, values


def resolve_agency_admin_password(fallback: str = "") -> str:
    """Login-Passwort: zuerst deploy.secrets.local, dann Prozess-Env."""
    _, values = _parse_file(secrets_path())
    pw = (values.get("AGENCY_ADMIN_PASSWORD") or "").strip()
    if pw:
        return pw
    return (os.getenv("AGENCY_ADMIN_PASSWORD", "") or fallback).strip()


def resolve_calcom_config(fallback_url: str = "") -> dict[str, str]:
    """Cal.com URL + API Key aus Secrets / Env."""
    _, values = _parse_file(secrets_path())
    url = (
        (values.get("CALCOM_URL") or "").strip()
        or (os.getenv("CALCOM_URL") or "").strip()
        or (fallback_url or "").strip()
    ).rstrip("/")
    key = (
        (values.get("CALCOM_API_KEY") or "").strip()
        or (os.getenv("CALCOM_API_KEY") or "").strip()
    )
    return {"url": url, "api_key": key}


def _rewrite_env_line(text: str, key: str, value: str) -> str:
    lines = text.splitlines()
    found = False
    out: list[str] = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            if not found:
                out.append(f"{key}={value}")
                found = True
            continue
        out.append(line.rstrip())
    if not found:
        out.append(f"{key}={value}")
    return "\n".join(out).rstrip() + "\n"


def sync_backend_env(keys: dict[str, str]) -> list[str]:
    """Wichtige Keys auch in backend/.env schreiben (sofort wirksam nach os.environ update)."""
    env_path = BACKEND_ENV
    if not env_path.parent.exists():
        local = Path(__file__).resolve().parent / ".env"
        if local.exists():
            env_path = local
        else:
            return []
    synced: list[str] = []
    try:
        text = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
        for key in ENV_SYNC_KEYS:
            if key not in keys:
                continue
            text = _rewrite_env_line(text, key, keys[key])
            os.environ[key] = keys[key]
            synced.append(key)
        if synced:
            env_path.write_text(text, encoding="utf-8")
    except OSError as exc:
        return [f"env_sync_error:{exc}"[:80]]
    return synced


def check_integrations_health(*, live: bool = False) -> dict:
    """Konfiguration + optional Live-Test für Watchdog."""
    _, values = _parse_file(secrets_path())
    checks: list[dict] = []

    smtp_ok = all(values.get(k) for k in ("AGENCY_SMTP_HOST", "AGENCY_SMTP_USER", "AGENCY_SMTP_PASS"))
    checks.append({"id": "smtp", "configured": smtp_ok})
    checks.append({"id": "stripe", "configured": bool(values.get("STRIPE_SECRET_KEY"))})
    checks.append({"id": "google_places", "configured": bool(values.get("GOOGLE_PLACES_API_KEY"))})
    checks.append({"id": "cloudflare", "configured": bool(values.get("CLOUDFLARE_API_TOKEN"))})
    checks.append({
        "id": "ionos",
        "configured": bool(values.get("IONOS_API_PREFIX")) and bool(values.get("IONOS_API_SECRET")),
    })
    checks.append({
        "id": "inwx",
        "configured": bool(values.get("INWX_USER")) and bool(values.get("INWX_PASSWORD")),
    })
    checks.append({"id": "hetzner", "configured": bool(values.get("HETZNER_API_TOKEN"))})
    checks.append({
        "id": "calcom",
        "configured": bool(values.get("CALCOM_API_KEY") or values.get("CALCOM_URL")),
    })
    checks.append({
        "id": "docuseal",
        "configured": bool(values.get("DOCUSEAL_API_TOKEN")),
    })
    checks.append({"id": "agency_login", "configured": bool(resolve_agency_admin_password())})
    checks.append({
        "id": "sms",
        "configured": bool(values.get("SMS_API_KEY"))
        and values.get("SMS_ENABLED", "").lower() in ("1", "true", "yes"),
    })
    checks.append({
        "id": "whatsapp",
        "configured": bool(values.get("WHATSAPP_ACCESS_TOKEN"))
        and bool(values.get("WHATSAPP_PHONE_NUMBER_ID")),
    })
    checks.append({
        "id": "telegram",
        "configured": bool(values.get("TELEGRAM_BOT_TOKEN"))
        and bool(values.get("TELEGRAM_OWNER_CHAT_ID") or values.get("TELEGRAM_OWNER_CHAT_IDS")),
    })
    checks.append({
        "id": "llm",
        "configured": bool(values.get("OLLAMA_URL") or values.get("OPENAI_API_KEY") or values.get("AUTO_HOST")),
    })

    failures: list[dict] = []
    for c in checks:
        if not c["configured"]:
            failures.append({"job": f"integration:{c['id']}", "reason": "not_configured"})

    if live:
        for test_id, fn in (
            ("smtp", test_smtp),
            ("google_places", test_google_places),
            ("stripe", test_stripe),
            ("cloudflare", test_cloudflare),
            ("ionos", test_ionos),
            ("inwx", test_inwx),
            ("hetzner", test_hetzner),
            ("docuseal", test_docuseal),
            ("sms", test_sms),
            ("whatsapp", test_whatsapp_meta),
        ):
            if not any(c["id"] == test_id and c["configured"] for c in checks):
                continue
            result = fn()
            if not result.get("ok"):
                failures.append({
                    "job": f"integration:{test_id}",
                    "reason": "live_test_failed",
                    "detail": result.get("error", "")[:160],
                })

    return {"ok": not failures, "checks": checks, "failures": failures}


def mask_value(value: str, *, secret: bool = True) -> str:
    if not value:
        return ""
    if not secret:
        return value if len(value) <= 40 else value[:20] + "…"
    if len(value) <= 8:
        return "••••••••"
    return value[:4] + "…" + value[-4:]


def get_status() -> dict:
    path = secrets_path()
    _, values = _parse_file(path)
    items = []
    for spec in KEY_CATALOG:
        val = values.get(spec["key"], "")
        is_secret = spec.get("input") == "password"
        items.append({
            **{k: v for k, v in spec.items() if not k.startswith("preset_")},
            "set": bool(val),
            "masked": mask_value(val, secret=is_secret) if val else "",
            "display": mask_value(val, secret=False) if val and not is_secret else "",
        })
    groups = []
    seen = set()
    for spec in KEY_CATALOG:
        g = spec["group"]
        if g not in seen:
            groups.append(g)
            seen.add(g)
    smtp_ok = all(values.get(k) for k in (
        "AGENCY_SMTP_HOST", "AGENCY_SMTP_USER", "AGENCY_SMTP_PASS"
    ))
    places_ok = bool(values.get("GOOGLE_PLACES_API_KEY"))
    return {
        "path": str(path),
        "exists": path.exists(),
        "items": items,
        "groups": groups,
        "smtp_configured": smtp_ok,
        "stripe_configured": bool(values.get("STRIPE_SECRET_KEY")),
        "google_places_configured": places_ok,
        "cloudflare_configured": bool(values.get("CLOUDFLARE_API_TOKEN")),
        "hetzner_configured": bool(values.get("HETZNER_API_TOKEN")),
        "docuseal_configured": bool(values.get("DOCUSEAL_API_TOKEN")),
        "agency_login_configured": bool(resolve_agency_admin_password()),
    }


def update_secrets(updates: dict[str, str]) -> dict:
    path = secrets_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return {"ok": False, "error": f"Verzeichnis nicht beschreibbar: {exc}"}

    lines, values = _parse_file(path)
    changed: list[str] = []

    for k, v in updates.items():
        if k not in ALLOWED_KEYS:
            continue
        v = (v or "").strip()
        if not v:
            continue
        if values.get(k) != v:
            values[k] = v
            changed.append(k)

    if not changed:
        return {"ok": True, "changed": [], "message": "Nichts geändert (leere Felder ignoriert)"}

    out_lines: list[str] = []
    seen: set[str] = set()
    if lines:
        for line in lines:
            s = line.strip()
            if s and not s.startswith("#") and "=" in s:
                key = line.split("=", 1)[0].strip()
                if key in values and key in ALLOWED_KEYS:
                    out_lines.append(f"{key}={values[key]}")
                    seen.add(key)
                    continue
            out_lines.append(line.rstrip())
    else:
        out_lines.append("# Webschmiede deploy.secrets.local · Agency Setup Portal")

    for spec in KEY_CATALOG:
        key = spec["key"]
        if key in values and key not in seen:
            out_lines.append(f"{key}={values[key]}")
            seen.add(key)

    text = "\n".join(out_lines).rstrip() + "\n"
    try:
        path.write_text(text, encoding="utf-8")
        path.chmod(stat.S_IMODE(0o600))
    except OSError as exc:
        return {"ok": False, "error": f"Speichern fehlgeschlagen: {exc}"}

    synced = sync_backend_env({k: values[k] for k in changed if k in ENV_SYNC_KEYS})
    result: dict = {"ok": True, "changed": changed, "path": str(path)}
    if synced:
        result["env_synced"] = synced
    return result


def _smtp_config(values: dict) -> dict | None:
    host = values.get("AGENCY_SMTP_HOST")
    user = values.get("AGENCY_SMTP_USER")
    password = values.get("AGENCY_SMTP_PASS")
    if not host or not user or not password:
        return None
    return {
        "host": host,
        "port": int(values.get("AGENCY_SMTP_PORT", "587") or "587"),
        "user": user,
        "password": password,
        "from": values.get("AGENCY_SMTP_FROM") or user,
        "reply_to": values.get("AGENCY_REPLY_TO", ""),
    }


def test_smtp(to_email: str | None = None) -> dict:
    from agency_mail import load_agency_smtp, send_html_email
    from email_templates import smtp_test_email

    _, values = _parse_file(secrets_path())
    cfg = _smtp_config(values)
    if not cfg:
        return {"ok": False, "error": "SMTP unvollständig (Host, User, Passwort)"}

    to = (to_email or values.get("AGENCY_OWNER_EMAIL") or cfg["user"]).strip()
    if not to:
        return {"ok": False, "error": "Keine Ziel-E-Mail. AGENCY_OWNER_EMAIL setzen"}

    reply = values.get("AGENCY_REPLY_TO") or cfg["user"]
    subject, text, html = smtp_test_email(reply_email=reply)

    try:
        send_html_email(to=to, subject=subject, html=html, text=text)
        return {"ok": True, "message": f"Test-Mail gesendet an {to}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def test_google_places() -> dict:
    _, values = _parse_file(secrets_path())
    key = values.get("GOOGLE_PLACES_API_KEY", "")
    if not key:
        return {"ok": False, "error": "GOOGLE_PLACES_API_KEY nicht gesetzt"}

    import requests

    try:
        r = requests.get(
            "https://maps.googleapis.com/maps/api/place/findplacefromtext/json",
            params={
                "input": "Mechernich",
                "inputtype": "textquery",
                "fields": "name",
                "key": key,
            },
            timeout=15,
        )
        data = r.json()
        st = data.get("status")
        if st == "OK":
            return {"ok": True, "message": "Google Places API funktioniert"}
        return {"ok": False, "error": f"Google API: {st} · {data.get('error_message', '')}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


def test_stripe() -> dict:
    _, values = _parse_file(secrets_path())
    key = values.get("STRIPE_SECRET_KEY", "")
    if not key:
        return {"ok": False, "error": "STRIPE_SECRET_KEY nicht gesetzt"}
    try:
        import stripe

        stripe.api_key = key
        stripe.Account.retrieve()
        mode = "Test" if key.startswith("sk_test_") else "Live"
        return {"ok": True, "message": f"Stripe verbunden ({mode}-Modus)"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


def test_cloudflare() -> dict:
    _, values = _parse_file(secrets_path())
    token = values.get("CLOUDFLARE_API_TOKEN", "")
    if not token:
        return {"ok": False, "error": "CLOUDFLARE_API_TOKEN nicht gesetzt"}
    import requests

    try:
        r = requests.get(
            "https://api.cloudflare.com/client/v4/user/tokens/verify",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        data = r.json()
        if data.get("success") and (data.get("result") or {}).get("status") == "active":
            return {"ok": True, "message": "Cloudflare Token gültig"}
        err = (data.get("errors") or [{}])[0]
        return {"ok": False, "error": err.get("message") or "Token ungültig"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


def test_ionos() -> dict:
    """IONOS Hosting DNS API: Präfix + Secret als X-API-Key."""
    _, values = _parse_file(secrets_path())
    prefix = (values.get("IONOS_API_PREFIX") or "").strip()
    secret = (values.get("IONOS_API_SECRET") or "").strip()
    if not prefix or not secret:
        return {"ok": False, "error": "IONOS_API_PREFIX / IONOS_API_SECRET fehlen"}
    # Falls jemand schon prefix.secret in ein Feld geklebt hat
    if "." in prefix and not secret:
        prefix, secret = prefix.split(".", 1)
    key = f"{prefix}.{secret}" if not prefix.endswith(secret) else prefix
    if "." not in key:
        key = f"{prefix}.{secret}"
    import requests

    try:
        r = requests.get(
            "https://api.hosting.ionos.com/dns/v1/zones",
            headers={"X-API-Key": key, "Accept": "application/json"},
            timeout=20,
        )
        if r.status_code == 200:
            zones = r.json() if r.content else []
            n = len(zones) if isinstance(zones, list) else "?"
            return {"ok": True, "message": f"IONOS DNS OK ({n} Zone(n))"}
        if r.status_code in (401, 403):
            return {"ok": False, "error": "IONOS Key ungültig oder keine DNS-Rechte"}
        return {"ok": False, "error": f"HTTP {r.status_code}: {r.text[:120]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


def test_inwx() -> dict:
    _, values = _parse_file(secrets_path())
    try:
        from integrations.inwx import test_connection
    except ImportError:
        from app.backend.integrations.inwx import test_connection  # type: ignore
    return test_connection(values)


def test_hetzner() -> dict:
    _, values = _parse_file(secrets_path())
    token = values.get("HETZNER_API_TOKEN", "")
    if not token:
        return {"ok": False, "error": "HETZNER_API_TOKEN nicht gesetzt"}
    import requests

    try:
        r = requests.get(
            "https://api.hetzner.cloud/v1/servers",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        if r.status_code == 401:
            return {"ok": False, "error": "Token ungültig oder abgelaufen"}
        if r.status_code >= 400:
            return {"ok": False, "error": f"Hetzner HTTP {r.status_code}: {r.text[:120]}"}
        data = r.json()
        servers = data.get("servers") or []
        names = ", ".join(s.get("name", "?") for s in servers[:8]) or "(keine Server)"
        extra = f" (+{len(servers) - 8})" if len(servers) > 8 else ""
        return {
            "ok": True,
            "message": f"Hetzner OK · {len(servers)} Server: {names}{extra}",
            "server_count": len(servers),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


def test_docuseal() -> dict:
    """X-Auth-Token gegen /api/templates (self-host oder Cloud)."""
    import urllib.error
    import urllib.request

    _, values = _parse_file(secrets_path())
    token = (values.get("DOCUSEAL_API_TOKEN") or "").strip()
    base = (values.get("DOCUSEAL_URL") or "https://sign.digitalehandwerkskunst.de").strip().rstrip("/")
    if not token:
        return {"ok": False, "error": "DOCUSEAL_API_TOKEN nicht gesetzt"}

    if "api.docuseal." in base or base.rstrip("/").endswith("docuseal.com") or base.rstrip("/").endswith("docuseal.eu"):
        url = "https://api.docuseal.com/templates"
        if "docuseal.eu" in base:
            url = "https://api.docuseal.eu/templates"
    else:
        url = f"{base}/api/templates"

    try:
        req = urllib.request.Request(
            url,
            headers={"X-Auth-Token": token, "Accept": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            raw = resp.read().decode("utf-8", "replace") or "[]"
        data = json.loads(raw)
        if isinstance(data, list):
            n = len(data)
        elif isinstance(data, dict):
            n = len(data.get("data") or data.get("templates") or [])
        else:
            n = 0
        return {"ok": True, "message": f"DocuSeal API OK · {n} Vorlagen · Token gültig"}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:180]
        hint = ""
        if e.code in (401, 403):
            hint = " Token falsch, oder Cloud-Token mit Self-Host-URL (bzw. umgekehrt)."
        return {"ok": False, "error": f"HTTP {e.code}: {body}{hint}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:220]}


def test_sms() -> dict:
    """seven.io Test an OWNER_PHONE (Secrets-Datei → Env für messaging)."""
    _, values = _parse_file(secrets_path())
    # Temporär Env aus Secrets (Prozess kann altes Env haben)
    for k in ("SMS_API_KEY", "SMS_SENDER", "OWNER_PHONE", "SMS_ENABLED"):
        if values.get(k):
            os.environ[k] = values[k]
    import messaging as messaging_svc

    return messaging_svc.test_sms()


def test_whatsapp_meta() -> dict:
    """Meta Graph: Phone Number ID prüfen (+ optional Text-Nachricht)."""
    _, values = _parse_file(secrets_path())
    for k in (
        "WHATSAPP_ACCESS_TOKEN",
        "WHATSAPP_PHONE_NUMBER_ID",
        "OWNER_PHONE",
    ):
        if values.get(k):
            os.environ[k] = values[k]
    import messaging as messaging_svc

    check = messaging_svc.verify_meta_phone()
    if not check.get("ok"):
        return check
    # Keine erzwungene Outbound-Nachricht (24h-Fenster) — Meta-Check reicht
    return check


def test_telegram() -> dict:
    """Telegram getMe + optional Ping an Owner-Chat."""
    _, values = _parse_file(secrets_path())
    for k in (
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_OWNER_CHAT_ID",
        "TELEGRAM_OWNER_CHAT_IDS",
        "TELEGRAM_WEBHOOK_SECRET",
    ):
        if values.get(k):
            os.environ[k] = values[k]
    import telegram_ops as tg

    ready = tg.readiness()
    if not ready.get("bot_token"):
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN fehlt"}
    try:
        import requests

        r = requests.get(
            f"https://api.telegram.org/bot{tg.bot_token()}/getMe",
            timeout=15,
        )
        data = r.json() if r.content else {}
        if not data.get("ok"):
            return {
                "ok": False,
                "error": (data.get("description") or r.text)[:200],
                "readiness": ready,
            }
        bot = data.get("result") or {}
        ping = None
        if ready.get("owner_chats"):
            ping = tg.notify_owner("Nils · Telegram-Test OK. Funnel-Pings kommen hier an.")
        return {
            "ok": True,
            "bot": {"username": bot.get("username"), "id": bot.get("id")},
            "readiness": ready,
            "ping": ping,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:160], "readiness": ready}
