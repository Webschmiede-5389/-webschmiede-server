# Direction — Webschmiede Server

> **Einstieg:** Dieses Dokument ist der Kompass für `My_Company_Hub/projects/webschmiede-server`.  
> Alles Weitere hängt an den Ordnern und Docs unten — kein Ratespiel in neuen Chats.  
> Firmen-Hub: `My_Company_Hub/` (Standards, Routing) · Workspace: `My_Company_Hub.code-workspace`

---

## Was ist dieser Ordner?

**Agency-Engine** für Webschmiede (Digitale Handwerkskunst):

- Live-Kunden (aktuell: **SHY001 Snack House Yassine**)
- Deploy, Backend, Admin, Bot, CRM, n8n
- Kunden-Onboarding (Handout + E-Mail)

**Nicht hier:** Video-Creator, Golf Guide, Wunschkennzeichen → eigene Spokes unter `My_Company_Hub/projects/` (siehe [webschmiede-workspace.md](webschmiede-workspace.md)).

---

## Ordner-Karte

```
Server/
├── docs/
│   ├── DIRECTION.md              ← Du bist hier (Kompass)
│   ├── webschmiede-workspace.md  ← Welcher Jarvis-Ordner wann?
│   ├── webschmiede-vision.md     ← Strategie & Produkt-Roadmap
│   ├── GITHUB.md                 ← Repo & Cloud Agents
│   └── agency/                   ← Rechnung, Seminare, Briefing
│       ├── seminare.md
│       └── nacht-briefing.md
│       ├── README.md
│       ├── mitarbeiter-stellenplan.md
│       ├── trend-scout.md
│       └── SHY001-uebergabe-handout.*
├── kunden/
│   └── SHY001_snackhouse.json    ← Kunden-Config (Links, Kontakt, Status)
├── agency-web/                   ← digitalehandwerkskunst.de (Replit-Quellcode)
│   └── README.md
├── app/
│   ├── backend/                  ← Flask API
│   ├── static/                   ← order, admin, index
│   └── jarvis/                   ← Bot, menu_catalog
├── scripts/
│   ├── extract_menu_catalog.py
│   └── send_onboarding_email.py
├── infra/n8n/                    ← Workflow-Vorlagen
├── jarvis.py                     ← Agency CLI
├── deploy.py                     ← Upload → Hetzner
├── setup_*.py                    ← Server-Setup (n8n, security, …)
├── agency_config.py              ← SSH-Secrets
├── agency_email.py               ← Onboarding-Mail (Agency-SMTP)
└── deploy.secrets.local          ← Gitignored (SSH + SMTP)
```

---

## Befehle (täglich)

| Aufgabe | Befehl |
|---------|--------|
| Kundenliste | `python jarvis.py kunden` |
| Kundendetails | `python jarvis.py kunde SHY001` |
| Neuer Kunde | `python jarvis.py neu` |
| Nächste Kunden-ID | `python jarvis.py next-id handwerk` |
| Deploy | `python deploy.py` |
| Onboarding-Mail (Vorschau) | `python jarvis.py onboard SHY001 --dry-run` |
| Onboarding-Mail senden | `python jarvis.py onboard SHY001 --upload-handout --support-email du@…` |
| **Go-Live Check** | `python scripts/go_live.py SHY001 check` |
| **Go-Live komplett** | `python scripts/go_live.py SHY001 run --support-email du@…` |
| **Seminare prüfen** | `python scripts/verify_seminars.py` |
| **Agency Env setzen** | `python scripts/setup_agency_env.py` |
## n8n (pro Kunde)

Beim Anlegen (`jarvis.py neu` oder Agency-Dashboard) werden automatisch Kunden-Workflows erstellt.

```bash
python jarvis.py n8n SHY001    # manuell nachziehen
python scripts/provision_kunde_n8n.py HWK001 --dry-run
```

Agency-Setup (einmalig):

```bash
python scripts/setup_n8n_buchhaltung.py
```

Details: [KUNDEN-ID.md](kunden/KUNDEN-ID.md) · [infra/n8n/README.md](../infra/n8n/README.md)
| **Cal.com installieren** | `python setup_calcom.py` |
| SMS + Review konfigurieren | `python scripts/go_live.py SHY001 configure --owner-phone +49… --sms-key KEY` |
| Testbestellungen | `python scripts/go_live.py SHY001 test-orders` |
| Menü-Preise aktualisieren | `python scripts/extract_menu_catalog.py` → dann `deploy.py` |

---

## Kunden-Lebenszyklus

```
1. jarvis.py neu          → kunden/SHY00X.json
2. Anpassen + deploy.py   → Server live
3. Handout anpassen       → docs/kunden/SHY00X-uebergabe-handout.html
4. onboard --upload       → E-Mail + Handbuch-Link an Kunden
5. Admin-Passwort         → separat WhatsApp/Telefon (nie E-Mail)
6. Go-Live                → status in JSON auf "live"
```

Details Handout: [kunden/README.md](kunden/README.md)  
Go-Live Call: [kunden/SHY001-go-live.md](kunden/SHY001-go-live.md)

---

## Links SHY001 (Test)

| Was | URL |
|-----|-----|
| Website | https://yassine.digitalehandwerkskunst.de/ |
| Bestellen | https://yassine.digitalehandwerkskunst.de/bestellen |
| Admin | https://yassine.digitalehandwerkskunst.de/admin |
| **Seminare** | https://digitalehandwerkskunst.de/seminare |
| **Agency Admin** | https://digitalehandwerkskunst.de/agency |
| **Agency Hub** | https://digitalehandwerkskunst.de/agency-hub |
| **Cal.com (1:1)** | https://cal.digitalehandwerkskunst.de |
| n8n | https://digitalehandwerkskunst.de/n8n/ |
| Handbuch (nach `--upload-handout`) | https://yassine.digitalehandwerkskunst.de/uebergabe-handbuch.html |

---

## Secrets & E-Mail

| Datei | Inhalt |
|-------|--------|
| `deploy.secrets.local` | SSH + **AGENCY_SMTP_*** + optional `AGENCY_ADMIN_PASSWORD` |
| `agency-credentials.local.txt` | Generiertes Agency-Admin-PW (gitignored) |
| Server `/root/app/backend/.env` | Admin-PW, SMS, Stripe (Gast-Mails) |

Vorlage: `deploy.secrets.local.example`

**Zwei Mail-Kanäle:**

- **Agency** (`onboarding@webschmiede.de`) → Willkommen, Handout, Support
- **Kunde** (`bestellung@…`) → Bestellbestätigungen an Gäste

---

## Docs-Index

| Dokument | Wann lesen |
|----------|------------|
| [DIRECTION.md](DIRECTION.md) | Einstieg, Ordner, Befehle |
| [webschmiede-workspace.md](webschmiede-workspace.md) | Mehrere Jarvis-Projekte / Cursor-Chats |
| [webschmiede-vision.md](webschmiede-vision.md) | Langfrist: Hub, Akquise, Branchen |
| [GITHUB.md](GITHUB.md) | Push, Private Repo, Cloud Agent |
| [agency/seminare.md](agency/seminare.md) | Seminar-System, API, Cal.com |
| [agency/nacht-briefing.md](agency/nacht-briefing.md) | Stand nach Nacht-Arbeit |
| [agency/messaging-ghl-ersatz.md](agency/messaging-ghl-ersatz.md) | SMS + WhatsApp statt GHL |
| [memory/README.md](memory/README.md) | Agency-Gedächtnis: CURRENT, Handoff, Topics |
| [b2b-euro-trading/README.md](b2b-euro-trading/README.md) | Händler-Radar / Wholesale DE+EU |

---

## Cursor-Chat Regel

**In diesem Ordner (`Server/`):** Snack House, Deploy, Backend, Onboarding, n8n.  
**Neuer Chat** wenn Thema wechselt oder der Chat zu voll ist — Agent schreibt `docs/memory/HANDOFF.md` und schlägt den Neustart vor (kann den Chat nicht selbst öffnen).  
**Vor dem Weiterarbeiten in neuem Chat:** `docs/memory/CURRENT.md` lesen.

Agent-Regeln: `AGENTS.md` · Rule: `.cursor/rules/wissen-und-chats.mdc`

---

## Offen (SHY001)

Aus `kunden/SHY001_snackhouse.json`:

- [ ] Agency-SMTP in `deploy.secrets.local`
- [ ] SMS (seven.io) + OWNER_PHONE
- [ ] Domain + HTTPS
- [ ] Google Review Link
- [ ] Stripe
- [ ] GitHub Repo → Private

---

*Webschmiede · Digitale Handwerkskunft · Stand Juli 2026*
