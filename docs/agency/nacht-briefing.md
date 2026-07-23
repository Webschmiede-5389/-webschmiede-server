# Gute-Nacht-Briefing — Was läuft, was morgen wartet



> Stand: 15. Juli 2026 (Nacht) · Du schläfst — Server & Plan bleiben.



---



## Was **heute Nacht** erledigt wurde (ohne dich)



| Was | Status |

|-----|--------|

| **Seminar-System** | ✅ Live: `/seminare`, `/agency`, API |

| **Agency-Passwort** | ✅ Neu generiert → `agency-credentials.local.txt` |

| **Server .env** | ✅ `AGENCY_ADMIN_PASSWORD`, `N8N_SEMINAR_WEBHOOK`, `CALCOM_URL` |

| **n8n Workflows** | ✅ Import versucht (alle `infra/n8n/workflow-*.json`) |

| **Cal.com** | ⏳ `setup_calcom.py` gestartet (Docker, dauert) |

| **Doku** | ✅ `docs/agency/seminare.md`, DIRECTION aktualisiert |



**Zugangsdaten lokal (gitignored):**



- `agency-credentials.local.txt` — Agency Admin Passwort + URLs

- `n8n-credentials.local.txt` — n8n Login

- `calcom-credentials.local.txt` — nach Cal.com-Setup



---



## Wichtig: Was **nicht** alleine „über Nacht baut“



| Was | Ohne dich aktiv? |

|-----|------------------|

| **Dieser Cursor-Chat** | ❌ Stoppt, wenn PC/Cursor zu ist |

| **Cloud Agent (GitHub)** | ✅ Nur wenn Repo **private** + Agent gestartet |

| **Hetzner Server** | ✅ API, n8n, Cron laufen 24/7 |

| **E-Mails an Kunden** | ❌ Braucht `AGENCY_SMTP_*` in deploy.secrets.local |

| **SMS Hassan** | ❌ Braucht seven.io Key + OWNER_PHONE |



---



## Links (morgen öffnen)



| Was | URL |

|-----|-----|

| Seminare (öffentlich) | https://digitalehandwerkskunst.de/seminare |
| Agency Admin | https://digitalehandwerkskunst.de/agency |
| Cal.com (1:1) | https://cal.digitalehandwerkskunst.de |
| Snack House Admin | https://yassine.digitalehandwerkskunst.de/admin |
| n8n | https://digitalehandwerkskunst.de/n8n/ |



Passwort Agency: siehe `agency-credentials.local.txt`



---



## Morgen-Checkliste (15 Min.)



```

□ agency-credentials.local.txt öffnen → Agency Admin testen

□ python scripts/verify_seminars.py

□ Cal.com: /cal/ öffnen → Admin-Account anlegen → Google Calendar verbinden

□ n8n: SMTP-Credential für E-Mail-Nodes setzen (falls Workflows importiert)

□ Agency-SMTP in deploy.secrets.local (Seminar-Bestätigungs-Mails)

□ python scripts/go_live.py SHY001 check

□ Hassan: Verkaufsblatt + SMS-Link (wenn seven.io da)

```



---



## Nächste Level — Agentur (Priorität)



### Phase 1 — Geld & Ordnung (diese Woche)

- [ ] Erste **Rechnung** an SHY001 (`docs/agency/rechnung-vorlage.html`)

- [ ] **Agency-SMTP** in `deploy.secrets.local`

- [ ] **seven.io** → Go-Live Hassan

- [ ] Cal.com Buchungslink auf webschmiede.de verlinken



### Phase 2 — Automatisierung (n8n)

- [x] Seminar-Anmeldung → Webhook (`workflow-seminar-anmeldung.json`)

- [ ] Neue Bestellung → SMS/E-Mail (Workflow importiert, SMTP fehlt)

- [ ] Monatsreport + Beleg-Archiv (Templates da)



### Phase 3 — Skalierung

- [ ] `jarvis.py neu` → zweiter Gastro-Kunde

- [ ] Domain + HTTPS für Snack House

- [ ] GitHub Repo → Private (Cloud Agent)



---



## Befehle für morgen



```bash

python scripts/verify_seminars.py      # Alles OK?

python scripts/go_live.py SHY001 check

python deploy.py                       # Nach Code-Änderungen

python setup_calcom.py                 # Falls Cal.com noch nicht läuft

python scripts/import_n8n_workflows.py # Workflows neu importieren

```



---



## Ein Satz zum Einschlafen



> Seminare sind live, der Server wartet. Morgen: Passwort öffnen, Cal.com klicken, Hassan anrufen — dann rollt die Agentur.



Gute Nacht.


