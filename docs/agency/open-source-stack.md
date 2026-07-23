# Open-Source Stack (Agency)

Stand: 2026-07-18

## Schon vorher

| Tool | URL / Ort | Zweck |
|------|-----------|--------|
| n8n | auto-01 `/opt/n8n` | Automation |
| Cal.com | https://cal.digitalehandwerkskunst.de | Termine |
| Voice-Demo | auto-01 :8090 | Günstige Voice-Demos |
| Eigenes CRM | Flask `contacts` | Kunden, kein GHL |

## Neu installiert (heute)

| Tool | URL | Zweck |
|------|-----|--------|
| **Umami** | https://analytics.digitalehandwerkskunst.de | Privacy-Analytics (DSGVO), kein Google Analytics |
| **DocuSeal** | https://sign.digitalehandwerkskunst.de | Angebote/Verträge digital unterschreiben |

Setup-Skripte: `scripts/setup_umami.py`, `scripts/setup_docuseal.py`  
Secrets nur auf Server: `/opt/umami/.credentials.local`, `/opt/docuseal/.credentials.local`

### Erste Schritte Christian

1. Umami: Login `admin@umami.is` / `umami` → **Passwort sofort ändern** → Website digitalehandwerkskunst.de anlegen → Tracking-Snippet in Agency-Site
2. DocuSeal: Admin + API-Token OK. **4 Vertrags-Vorlagen live** (Angebot, Auftrag, AGB, AVV) unter https://sign.digitalehandwerkskunst.de/templates · Details `docs/agency/vertraege/README.md`. Template-Create-API ist Pro; Anlage läuft über Rails/PDF.

## Bewusst noch nicht (warten / eigener Entscheid)

| Tool | Warum warten |
|------|----------------|
| Twenty CRM | Eigenes CRM existiert; Doppelstruktur vermeiden |
| Chatwoot | Stark, aber schwer; erst Messaging (WA/SMS) fertig |
| Listmonk | Newsletter; nach SMTP-Routinen sinnvoll |
| Plane / Penpot | Projekt/Design; nicht Umsatz-kritisch jetzt |

## Install-Regel

Kein Auto-Install ohne OK. Heute: Christian hat OSS-Install freigegeben.
