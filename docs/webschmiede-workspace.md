# Webschmiede – Ordner & Cursor-Workflow

> Kurzanleitung: Wo arbeitest du wann? Welcher Chat? Welches Repo?

## Deine aktuelle Struktur (Hub & Spoke)

```
Jarvis/
└── My_Company_Hub/                    ← Unternehmens-Hub
    ├── core/, management/, infrastructure/
    └── projects/
        ├── webschmiede-server/        ← Agency-Engine + SHY001 (dieser Spoke)
        ├── wunschkennzeichen/
        ├── german-golf-guide/
        ├── landingpage-manager/
        ├── video-creator/
        └── picture-optimizer/
```

**Regel:** Ein Spoke = ein Workspace-Root = ein Hauptthema.

**Hub:** `My_Company_Hub/` für Strategie, Standards, Inventar. Siehe `../../README.md` (Hub-Root).

---

## Wann welcher Ordner?

| Du willst … | Ordner öffnen | Beispiel-Chat-Titel |
|-------------|---------------|---------------------|
| Firmen-Standards, Inventar, Hub-Routing | `My_Company_Hub/` | „Hub — DNS-Standard“ |
| Bestellportal, Admin, Deploy, Bot, n8n | `projects/webschmiede-server/` | „Snack House – Security“ |
| Neuen Kunden anlegen, Jarvis CLI | `projects/webschmiede-server/` | „Neuer Kunde – Bäckerei XY“ |
| Strategie, Roadmap (Detail) | `docs/webschmiede-vision.md` oder Hub | „Webschmiede Strategie Q3“ |
| Kennzeichen / Domain-Pipeline | `projects/wunschkennzeichen/` | „KW — INWX Provision“ |
| Social-Media (Golf Guide) | `projects/german-golf-guide/` | „Golf Guide – Content“ |
| Video-Content | `projects/video-creator/` | „Reel-Skript Gastro“ |
| GHL Landingpages (Legacy) | `projects/landingpage-manager/` | „GHL Page Setup“ |
| Bildoptimierung | `projects/picture-optimizer/` | „WebP Batch“ |

**Faustregel:** Code ändern oder deployen → **immer im passenden Ordner**.  
Nur Ideen sammeln → geht überall, aber zum Umsetzen den Ordner wechseln.

---

## Chats: neu oder hier weiter?

| Situation | Empfehlung |
|-----------|------------|
| Gleiches Projekt, gleiches Thema | **Chat hier weiter** |
| Neues Projekt / anderer Kunde | **Neuer Chat** im richtigen Ordner |
| Thema komplett gewechselt (z.B. Server → Video) | **Neuer Chat** + Ordner wechseln |
| Chat wird lang / unübersichtlich | Agent füllt `docs/memory/HANDOFF.md` und schlägt **neuen Chat** vor |
| Neuer Chat starten | Erste Nachricht: „lies docs/memory/CURRENT.md und HANDOFF.md“ oder den Handoff-Block |

**Kontext mitgeben (Copy-Paste-Vorlage):**

Siehe auch [memory/HANDOFF.md](memory/HANDOFF.md) (Agentur-Gedächtnis in `Jarvis/Server`).

```
Lies docs/memory/CURRENT.md und docs/memory/HANDOFF.md.
Ziel: …
```

Ältere Kurz-Vorlage:

```
Projekt: [Name, z.B. SHY001 Snack House]
Ordner: Jarvis/Server
Letzter Stand: [1 Satz]
Heute: [Was soll passieren?]
```

---

## GitHub & Cloud Agents

| Projekt-Typ | Repo |
|-------------|------|
| Agency + Kunden-Engine | `-webschmiede-server` (→ besser umbenennen, **Private**) |
| Eigenes Tool (LP Machine, Video …) | **Eigenes Repo pro Tool** |
| Kunde mit stark abweichendem Code | Optional eigenes Repo, sonst `kunden/*.json` + Template in Server |

**Cloud Agent** arbeitet nur im Repo, das du ihm gibst — nicht über alle Jarvis-Ordner hinweg.

---

## Was pro Projekt dokumentieren?

Damit ein **neuer Chat** sofort weiter kann:

| Datei | Inhalt |
|-------|--------|
| `README.md` | Was ist das? Wie starten/deployen? |
| `AGENTS.md` | Regeln für Cursor (Sprache, Stack, No-Gos) |
| `docs/` | Strategie, Setup, offene TODOs |
| `kunden/*.json` | Nur in Server — Kunden-Config |

Server hat das schon. Andere Jarvis-Ordner: bei Bedarf kurzes `README.md` + `AGENTS.md` nachziehen.

---

## Ziel-Struktur (erreicht)

```
My_Company_Hub/
├── … (Hub-Hirn)
└── projects/
    ├── webschmiede-server/
    ├── wunschkennzeichen/
    ├── german-golf-guide/
    ├── landingpage-manager/
    ├── video-creator/
    └── picture-optimizer/
```

**Workspace:** `My_Company_Hub/My_Company_Hub.code-workspace` öffnen.

---

## Schnell-Referenz für dich

1. **Einstieg / Kompass** → `Server/docs/DIRECTION.md`
2. **Snack House / Hetzner / Deploy** → `Server/` + Chat dort  
2. **Neues Kundenprojekt** → `Server/` + `python jarvis.py neu`
3. **Marketing-Tool bauen** → eigenes Tool-Verzeichnis
4. **Strategie lesen** → `Server/docs/webschmiede-vision.md`
5. **Wiederkehrende Agent-Regeln** → Skill `webschmiede-os` (global in Cursor)

---

## Nächste sinnvolle Schritte (optional)

- [ ] GitHub-Repo `Server` auf **Private** stellen  
- [ ] Pro Tool-Ordner ein kurzes `README.md`  
- [ ] Chat-Titel sprechend benennen (Cursor: Rechtsklick → Rename)
