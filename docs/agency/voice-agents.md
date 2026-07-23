# Voice Agents (Webschmiede)

Stand: Juli 2026 · Digitale Handwerkskunst

## Ziel

Telefon-Assistenten für lokale Betriebe (optional im Paket).  
Besser und branchenspezifischer als generische GHL-Voice.  
Demo günstig bei uns, echtes Geschäft über Retell.

## Zwei-Phasen-Modell

| Phase | Wo | Zweck | Kostenlogik |
|-------|-----|--------|-------------|
| **Demo** | Eigener Server / Web-Call | Vorführen, Branchen testen, Interessenten rumspielen lassen | Fast keine Minutenkosten |
| **Produktion** | Retell AI | Zahlende Kunden, echte Rufnummer, stabil 24/7 | Retell-Minuten aus Kunden-Monatsgebühr |

### Ablauf mit dem Kunden

1. Demo zeigen (Browser oder Demo-Nummer der Agentur).
2. Branche wählen (Gastro, Dach, Friseur, …) und Text/Wissen anpassen.
3. Optional: Stimme des Inhabers klonen (mit Erlaubnis) oder Agentur-Stimme (Christian).
4. Kunde bucht Voice-Paket.
5. Agent wird auf **Retell** angelegt, Nummer gebunden, n8n/SMS angebunden.
6. Demo bleibt für Akquise und nächste Gespräche.

## Stimmen

| Stimme | Nutzung |
|--------|---------|
| **Webschmiede Christian** (Clone) | Agentur-Demo, Hub, allgemeine Anrufe |
| **Kunden-Clone** | Optional, WhatsApp-Sprachnachricht 1–2 Min., nur mit Zustimmung |
| **Fertige DE-Stimme** | Fallback, wenn Clone hakelig klingt |

Clone-Vorlage und Kunden-Skript: im Chat / Übergabe hinterlegt (ruhige Aufnahme, klar sprechen).

## Branchen-Wissen

Pro Vertical ein Pack (wie `knowledge/packs/`):

- Öffnungszeiten, Adresse, typische FAQ
- Gastro: Bestell-Link, Ruhetag, Allergien-Hinweis
- Handwerk: Angebot, Notfall, Termin

Demo-Agent lädt das Pack je nach Branche.  
Produktions-Agent auf Retell bekommt dasselbe Wissen (Knowledge Base / Prompt).

## Technik

### Demo (eigene Seite)

- Web-Call im Browser (kein teurer Retell-Minutenzähler fürs Rumspielen)
- Später optional: eigener Voice-Mini-Server (STT + LLM + TTS)
- Steuerung und Nacharbeit: **n8n** + eigenes CRM/Portal
- WhatsApp / SMS: weiterhin eigene Stacks (Meta / seven.io), nicht über Retell nötig

### Produktion (Retell)

- Account: Agentur-Master (`RETELL_API_KEY` in `/agency-setup`)
- Pro Kunde: eigener Agent + Knowledge + optional Clone
- Rufnummer: über Retell (API aktuell vor allem US/CA) oder SIP später
- Webhook → n8n / Backend (SMS Bestell-Link, Mail an Inhaber, CRM)

Live-Demo Agentur (Stand Juli 2026):

- Agent: `Webschmiede Digitale Handwerkskunst`
- Agent-ID: `agent_9017e5879a197d4cae6011509c`
- Voice: `Webschmiede Christian` (`custom_voice_776939a71c0c6cbfdda7f5ac61`)
- Meta-Datei: `agency/retell_demo.json`

## Verkauf (Richtwerte)

Nicht Minuten verkaufen. Paket verkaufen.

| Paket | Monat ca. | Inhalt |
|-------|-----------|--------|
| Voice Basis | 99 € | Agent, Standard/Agentur-Stimme, FAQ, Bestell-Link-SMS |
| Voice Plus | 149–179 € | Bessere Stimme / Clone, mehr Minuten-Puffer |
| Voice Pro | 229–249 € | Premium, eng an Betriebsdaten, Reporting |

Einmalig Setup: 149–299 €.

Retell-Einkauf grob 0,10–0,20 $/Min. je nach Modell/Stimme.  
Marge = Paketpreis minus Retell minus SMS.

## Was wir nicht machen

- Stimmen von Retell/ElevenLabs „kopieren“ und selbst hosten (Verbot / technisch gesperrt)
- Domains oder Nummern kaufen ohne ausdrückliches OK von Christian
- Voice als Pflicht in jedem Portal-Paket (bleibt optional)
- Demo und Produktion vermischen (Demo darf billig und spielerisch sein, Produktion muss stabil sein)

## Eigenbau Demo (ohne Retell)

Stack vorbereitet unter `infra/voice-demo/` (Ollama + Whisper + DE-TTS + Web-UI).

Bereits wählbar (ohne großen Server schon im Repo):

- **10 Stimmen** Mann/Frau, DE/AT/CH (edge-tts)
- **9 Sprachstile** inkl. Kölsch, Platt, Bayrisch, Berlinerisch, AT, CH
- **Akzent-Verstehen** über Whisper-Hinweise + Modell `base`/`small`
- Branchen: general / gastro / handwerk

Grenze: Dialekt steckt im Text, nicht in echter Mundart-Aussprache der TTS.

- **Nicht** auf dem 2-GB-Shop-Server starten.
- Neuer Hetzner (min. 8 GB RAM) → `bash scripts/install_voice_demo.sh` (**nur Install, kein Start**)
- Später starten: `cd infra/voice-demo && docker compose up -d`
- Remote: `python scripts/remote_install_voice_demo.py` (braucht `VOICE_HOST`/`AUTO_HOST`/`WEB_HOST` in Secrets)
- Details: `infra/voice-demo/README.md`

## Checkliste Agentur

- [x] Retell API Key in `/agency-setup` (Gruppe Voice)
- [x] Agentur-Demo-Agent + Christian-Clone (Retell)
- [x] Eigenen Voice-Demo-Stack im Repo (`infra/voice-demo`)
- [x] Stimmen-Katalog + Dialekt-/Stil-Packs + UI-Umschalter
- [ ] Voice-Server bei Hetzner bestellen (8 GB+) und Setup-Skript laufen lassen
- [ ] Billing/Karte bei Retell (für Produktions-Nummer)
- [ ] Branchen-Packs erweitern
- [ ] n8n: nach Anruf SMS / Mail
- [ ] Angebotstext Voice in `angebote.json`
- [ ] Pro zahlendem Kunden: Retell-Agent + Nummer + Knowledge

## Verwandte Docs

- Knowledge Packs: `knowledge/packs/`
- Agency Setup: `/agency-setup`
- Cockpit Kanäle: `agency.html` (Voice Provider Retell/Vapi/…)
- Domains-Kaufregel analog: nie kostenpflichtig ohne Freigabe
