# Webschmiede Server – Agent Guide

This repo is the **agency infrastructure** for Webschmiede (Digital Craftsmanship). First live client: **Snack House Yassine (SHY001)**.

## Quick commands

```bash
python jarvis.py kunden          # list clients
python jarvis.py kunde SHY001    # client details
python jarvis.py neu             # new client wizard
python deploy.py                 # deploy to server (needs deploy.secrets.local)
python setup_crm_env.py          # CRM/SMS env on server
python setup_n8n.py              # n8n automation hub on server
```

**GitHub:** Repo initialized locally. Push: see `docs/GITHUB.md`. Secrets in `deploy.secrets.local` (gitignored).

## n8n (Automation Hub)

- **URL:** https://digitalehandwerkskunst.de/n8n/
- **Login:** see `n8n-credentials.local.txt` (local only, gitignored)
- **Workflow templates:** `infra/n8n/*.json` — import in n8n UI
- **Docs:** `infra/n8n/README.md`

## Stack

- **Frontend:** Static HTML (Tailwind CDN, Font Awesome, Bunny Fonts)
- **Backend:** Flask + SQLite (`app/backend/main.py`)
- **Server:** Nginx + systemd `snack-api` on port 8000
- **CRM:** Own `contacts` table – **not GoHighLevel** (`GHL_ENABLED=false`)
- **SMS:** seven.io (`SMS_ENABLED` in `.env`)

## Key files

| File | Purpose |
|------|---------|
| `app/static/order.html` | Customer order portal |
| `app/static/admin.html` | Client operations dashboard |
| `app/static/index.html` | Marketing website |
| `app/backend/main.py` | API, CRM, SMS, promos |
| `kunden/*.json` | Per-client config |
| `jarvis.py` | Agency CLI |
| `deploy.py` | Deployment |
| `app/backend/.env.example` | Required environment variables |

## Rules for agents

1. **German** responses to the user unless they use another language.
2. **No GHL** for new features – extend own CRM/SMS.
3. **DSGVO:** Bunny Fonts, no tracking, document third parties in `datenschutz.html`.
4. **Deploy:** Always run `deploy.py` after static/backend changes; verify `snack-api` active.
5. **Design:** Match existing dark/gold Snack House style; avoid generic AI aesthetics. Agency wordmark: only freigestelltes `/ci/webschmiede-logo.png` (see `docs/agency/ci/BRAND.md`).
6. **Scope:** Minimal diffs; don't refactor unrelated code.
7. **Ton:** Kunden-Texte und Mails menschlich, kein KI-Marketing — siehe `.cursor/rules/menschlicher-ton.mdc`.
8. **Betriebssicherheit:** Alles muss 24/7 zuverlässig laufen — Fehler früh erkennen, auto-reparieren, Inhaber informieren. Kunde ist nie First-Line-Support. Siehe `.cursor/rules/betriebssicherheit.mdc` (Smoke-Tests, Watchdog, klare Fehlermeldungen, kein stilles Scheitern).
9. **Gedächtnis:** Beschlüsse und aktueller Fokus in `docs/memory/` schreiben. Bei Chat-Überlast Handoff füllen und neuen Chat vorschlagen (Rule `wissen-und-chats.mdc`).
9. **Nils:** Ops-Mitarbeiter (KI), unter Stefan. Regel `.cursor/rules/nils.mdc`, Skill `.cursor/skills/nils/`, Handbuch `docs/agency/nils.md`.
10. **Stefan:** Betriebsleiter (KI). Tempo und Priorität. Regel `.cursor/rules/stefan.mdc`, Sheet `docs/agency/stefan.md`.

## Cursor skill

Full playbook for future projects: personal skill **`webschmiede-os`**  
(`~/.cursor/skills/webschmiede-os/SKILL.md` + `reference.md`)

**Multi-project workflow:** see `docs/webschmiede-workspace.md` (which folder, which chat, GitHub).

**Direction (start here):** `docs/DIRECTION.md` — folder map, commands, customer lifecycle, onboarding mail.

**Agency invoices (no sevDesk yet):** `docs/agency/rechnung-vorlage.html` · `docs/agency/angebot-vorlage.html`

## Status (July 2026)

### Done
- Order portal + admin dashboard (orders, promos, menu, printer, reports, push)
- Own CRM (`contacts`, `message_log`, Kunden tab)
- SMS automation ready (seven.io, needs API key)
- GHL disabled on server
- DSGVO pages, security headers, favicons
- Agency CLI + kunden.json
- **Stellenplan / Team-Radar:** `docs/agency/mitarbeiter-stellenplan.md`, `docs/agency/trend-scout.md`

### Planned
- Agency browser dashboard (jarvis web UI)
- PWA, loyalty, review funnel, WhatsApp promo control
- **Product vision (hub + niches):** see [`docs/webschmiede-vision.md`](docs/webschmiede-vision.md)
 - Sales wizard + forecast portal
 - Acquisition scanner (Akquise-Krieger) per vertical
 - Industry landings (`/gastro`, `/dach`, …) + separate Instagram per niche
 - Auto-onboarding after Stripe
 - Instagram post pipeline (approval queue)
 - FlyRuwe-style hub: one webschmiede.de, many industry spokes
 - **Trend Scout:** weekly DE-fit reports → niche recommendations (`docs/agency/trend-scout.md`)
 - **Social Pipeline (German Golf Guide):** n8n + Meta API — copy, design, schedule IG/FB; own comments only; no auto-engagement on third-party profiles — see vision doc


## Webschmiede-Standard: fester Umfang und sichtbare Abnahme

**Verbindlich ab 05.10.2026 für jeden Auftrag und jedes Projekt.**

Jeder Auftrag braucht vor Implementierung einen festen Umfang und einen vollständigen, sichtbaren Abnahmelauf. Festhalten: Nutzer/Ziel, Must-have, Out-of-Scope, sichtbarer Einstieg, Ablauf bis zum fachlichen Ergebnis, relevante Fehler-/Abbruchpfade und prüfbare Abschlusskriterien. Bei Aufgaben ohne UI ist der Nachweis das tatsächlich nutzbare Ergebnis im passenden Medium; keine künstliche Oberfläche bauen.

Den Umfang nicht still auf Foundation, Labels, APIs oder einen kleineren Slice reduzieren. Zusammenhängende autorisierte Arbeit bis zu den vereinbarten Kriterien ausführen; interne Schritte brauchen keine wiederholte Freigabe. Echte Blocker und Umfangsänderungen ausdrücklich benennen. Kein PASS bei fehlender Kernfunktion oder fehlendem gefordertem Nachweis.

Bei UI-Aufträgen auf der tatsächlich geöffneten URL prüfen: Port, Projektprozess, Arbeitsverzeichnis, Branch/Commit und lokale Änderungen dokumentieren. Ein anderer QA-Port beweist nicht den Nutzerstand. Sichtbare Navigation bis zum fachlichen Ergebnis testen, einschließlich passender Rollen, Geräte und Fehlerpfade. Eine Erfolgsmeldung ohne verarbeitetes Ergebnis ist kein Nachweis. Bestehende Daten erhalten und keine fremden Prozesse pauschal beenden.

Implementierung, ausgeführte Tests, vollständige Browserabnahme, externes Review, echter Nutzertest und Demo-/Live-Freigaben getrennt berichten. Screenshots/Aufnahmen und Dokumentation dem geprüften Stand zuordnen. Synthetischer PASS ersetzt keinen echten Nutzer.

Dieser Standard gilt auch für neue Projektvorlagen: in die projektspezifischen AGENTS-/Cursor-Regeln übernehmen und im Auftrag konkretisieren. Vorhandene Freigabegrenzen bleiben erhalten; die Regel autorisiert keinen Merge, Deploy, Versand oder Live-Zugriff. Offene Human-/Review-Abnahme blockiert nicht automatisch weitere reversible, bereits autorisierte Arbeit.

## Zwei getrennte Abnahmen: technische Funktion und selbstständige Bedienbarkeit

**Verbindliche Ergänzung vom 05.10.2026.** Ein technisch durchgeklickter Ablauf und ein selbstständig gefundener Ablauf sind unterschiedliche Nachweise. Bei UI-/Workflow-Aufträgen vor Implementierung für beide prüfbare Kriterien festlegen.

1. **Technische Abnahme:** Automatisierte Tests und vollständiger Browserlauf prüfen das fachliche Ergebnis sowie relevante Zustände, Fehler, Rechte, Persistenz und Deduplizierung auf dem identifizierten Build. Ein grüner Testlauf oder Agent-Browser-PASS bestätigt keine selbstständige Bedienbarkeit.
2. **Bedienbarkeitsprüfung vorab:** Einstieg, verständliche Begriffe, eindeutige Objekte, sichtbarer Zustand, nächste mögliche Aktion, Rückweg und Fehlervermeidung prüfen. Auch falsche Einstiege, gleichnamige Instanzen und Aktionen ohne erfüllte Voraussetzungen untersuchen. Bestehendes und Neues klar unterscheiden. Keine unzulässigen Aktionen scheinbar ausführbar anbieten; Sperrgründe erklären und serverseitig durchsetzen.
3. **Aufgabenbasierter echter Nutzertest:** Tatsächliche oder wahrscheinliche Nutzer erhalten Rolle, Situation und Ziel, aber keine Buttonnamen, Klickfolge, Direkt-URL zum Detail oder sonstige Lösungshinweise. Normale Hilfen innerhalb des Produkts dürfen genutzt werden. Beobachter lassen zunächst selbstständig arbeiten. Bei notwendiger Hilfe darf unterstützt werden; danach den Abschluss ausdrücklich als „mit Hilfe“ dokumentieren.
4. **Nachweis je Aufgabe:** „selbstständig geschafft / mit Hilfe geschafft / nicht geschafft“, benötigte Zeit, Fehlaktionen, Zögerstellen, Hilfe und fachliches Ergebnis festhalten. Akzeptanzkriterien und gegebenenfalls Zeitgrenzen vor dem Test aufgabenbezogen bestimmen, nicht nachträglich passend machen. Kleine Testrunden finden Probleme, beweisen aber keine allgemeine Erfolgsquote.
5. **Korrektur und erneute Abnahme:** Beobachtete Schwierigkeiten sind Produktbefunde, nicht automatisch Bedienfehler. Relevante Probleme innerhalb des vereinbarten Umfangs beheben, geeignete Regressionstests ergänzen und die Aufgabe erneut prüfen; für Erstnutzbarkeit möglichst mit einer Person ohne vorherige Klickanleitung. Keine endlose Ausweitung auf neue Module.
6. **Ehrlicher Status:** TECHNICAL_PASS, AGENT_BROWSER_PASS und HUMAN_USABILITY_PASS getrennt ausweisen. Fehlender Nutzertest bedeutet HUMAN_USABILITY_OPEN, Hilfe bedeutet ASSISTED, eine gescheiterte Kernaufgabe bedeutet FAIL für diese Aufgabe. Kein vollständiger UX-PASS bei offener oder gescheiterter verpflichtender Kernaufgabe. KI-Prüfung ergänzt echte Nutzerprüfung und ersetzt sie nicht. Offene Abnahme verhindert nicht automatisch weitere autorisierte reversible Arbeit; bestehende Merge-/Deploy-/Live-Grenzen bleiben bestehen.

**Vorlagenpflicht:** Jeder UI-/Workflow-Auftrag enthält getrennt den technischen Prüfablauf und ein neutrales Nutzerszenario ohne Lösungsweg. In Agentenregeln und neue Projektvorlagen übernehmen. Wiederholtes Erklären einer verwirrenden Oberfläche ersetzt keine Korrektur.

Methodische Grundlagen:
- GOV.UK, technische QA: https://www.gov.uk/service-manual/technology/quality-assurance-testing-your-service-regularly
- GOV.UK, moderierte Nutzertests: https://www.gov.uk/service-manual/user-research/using-moderated-usability-testing
- Nielsen Norman Group, neutrale Aufgaben: https://www.nngroup.com/articles/task-scenarios-usability-testing/
- Nielsen Norman Group, Usability-Heuristiken: https://www.nngroup.com/articles/ten-usability-heuristics/
- Playwright, sichtbares Nutzerverhalten: https://playwright.dev/docs/best-practices
- Forschungsbefund zu Grenzen synthetischer Walkthroughs (Preprint; kein allgemeiner Wirksamkeitsbeweis): https://arxiv.org/abs/2512.03568

## SELLABLE > PERFECT: begrenzter Umfang, belastbare Kernqualität, klarer Abschluss

**Verbindliche Konkretisierung vom 05.10.2026.** Verkaufsfähigkeit bezieht sich auf den ausdrücklich vereinbarten Einsatz. Eine vorführbare Offline-Demo ist kein Nachweis für produktive Integrationen oder dauerhaften Betrieb.

- Vor dem Build Kernaufgaben, Qualitäts-/Abnahmekriterien, Ausschlüsse und Aufwandgrenze festlegen. Technische Korrektheit, selbstständige Bedienbarkeit und Eignung für den vereinbarten Einsatz getrennt bewerten.
- Zusatzwünsche, kosmetische Verbesserungen und Zukunftsarchitektur zurückstellen, wenn sie die vereinbarte Kernaufgabe nicht verbessern. Keine endlose Perfektionsschleife.
- Bekannte Fehler, die die Kernaufgabe blockieren, irreführende Aktionen oder unbeabsichtigte folgenreiche Änderungen erzeugen, gehören zur Kernqualität und werden behoben. „SELLABLE > PERFECT“ rechtfertigt weder falsche Erfolgsanzeigen noch Sicherheits-/Datenfehler.
- Unter Zeitdruck zuerst ausdrücklich den optionalen Umfang reduzieren, statt Kernqualität still zu senken. Einen fest beauftragten Pflichtumfang niemals eigenmächtig kürzen; notwendige Änderungen als Entscheidung mit Folgen sichtbar machen.
- Automatisierte technische Tests, Browsernachweise und kurze aufgabenbasierte echte Nutzertests passend zum Risiko einsetzen. Keine eigene große QA-Plattform bauen, wenn bestehende Werkzeuge genügen. Kleine qualitative Nutzertestrunden finden Probleme; sie liefern keine statistische Garantie. Teilnehmerzahl und Rollen an Fragestellung und Risiko ausrichten.
- Befunde priorisieren: Kernaufgabe blockiert oder fachliches Ergebnis falsch → beheben; verständliche Aufgabe mit kleiner kosmetischer Unschönheit → dokumentieren und zurückstellen. Relevante Schwierigkeiten bei der ersten Benutzung zählen als Befunde, auch wenn ein Agent den vorgesehenen Klickweg schafft.
- Nach einem Fix die betroffenen Aufgaben und passende Regressionen erneut prüfen. Bereits bestandene Prüfungen nur bei neuen Änderungen, Fehlern oder begründeten offenen Risiken ausweiten oder wiederholen.
- Nach erfüllten vereinbarten Kriterien den Auftrag schließen. Keine weiteren Features anhängen. Offene Review-/Human-/Live-Grenzen eindeutig ausweisen; Implementierungsabschluss nicht mit Produktionsfreigabe verwechseln.
- Auftragsvorlagen enthalten: Ziel/Kernaufgaben, Ausschlüsse, Aufwandgrenze, technische Nachweise, neutrales Nutzerszenario, Priorisierung der Befunde und Stop-Kriterium. Neue Erkenntnisse außerhalb des Umfangs ins Parking Lot aufnehmen.

Übertragene Praxis, keine allgemeine Fehlerfreiheitsgarantie:
- Basecamp / Shape Up — Umfang und Zeitgrenzen: https://basecamp.com/shapeup/1.2-chapter-03
- Basecamp / Shape Up — Abschlussentscheidung: https://basecamp.com/shapeup/3.5-chapter-14
- GitLab — Qualitätsmaßstab: https://handbook.gitlab.com/handbook/product/product-principles/
- GitLab — Nutzeraufgaben und Ergebnisse: https://handbook.gitlab.com/handbook/product/ux/jobs-to-be-done/jtbd-playbook/
- GOV.UK — passende Nutzertestrunden: https://www.gov.uk/service-manual/user-research/plan-user-research-for-your-service
