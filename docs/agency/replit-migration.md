# Replit → Cursor: Agency-Website übernehmen

> Ziel: [digitalehandwerkskunst.de](https://digitalehandwerkskunst.de/) in `agency-web/` bearbeiten und deployen — getrennt vom Hassan-Server.

---

## Was die Live-Seite ist

- **Stack:** React + Vite (Single Page App)
- **Build:** `/assets/index-*.js` + CSS (minified)
- **Hosting:** Google Frontend (typisch Replit Deploy oder Firebase) — **nicht** der Hetzner-Server
- **Inhalt:** Handwerk-Agentur, Christian Kummetat, Pakete (Basis → Platin/Robert)

**Ohne Replit-Export** haben wir nur den minified Build — Cursor kann damit kaum sinnvoll weiterarbeiten.

---

## Schritt 1 — ZIP aus Replit

1. https://replit.com → dein WebSchmiede-Projekt
2. Links: **Files** → oben **⋮** → **Download as ZIP**
3. ZIP nach `Jarvis/Server/agency-web/` entpacken
4. Prüfen: `package.json` und Ordner `src/` liegen direkt unter `agency-web/`

Falls die ZIP einen Unterordner hat (z. B. `WebSchmiede-main/`), Inhalt **eine Ebene hoch** verschieben.

---

## Schritt 2 — Lokal testen

```bash
cd agency-web
npm install
npm run dev
```

Browser: meist http://localhost:5173

---

## Schritt 3 — Cursor

Neuer Chat optional: *„Agency-Website in agency-web/ — lies README“*

Dann können wir:

- Texte/Pakete/Design anpassen
- Gastro-Referenz (Snack House) als Case Study verlinken
- Deploy-Script bauen
- Impressum/Datenschutz synchron halten

---

## Schritt 4 — Deploy (du entscheidest)

| Option | Aufwand | Empfehlung |
|--------|---------|--------------|
| **Replit Deploy behalten** | Gering | Code hier, `git push` → Replit synced (wenn GitHub angebunden) |
| **Hetzner + nginx** | Mittel | Volle Kontrolle, eine Infrastruktur mit Kunden-API |
| **Firebase/Netlify** | Mittel | Wenn schon an digitalehandwerkskunst.de gehängt |

DNS `digitalehandwerkskunst.de` erst umstellen, wenn der neue Build getestet ist.

---

## Ordner-Trennung (Jarvis/Server)

```
Server/
├── agency-web/          ← DEINE Agency-Website (Replit-Quellcode)
├── app/static/          ← Kunden-Sites (Snack House order/admin)
├── app/backend/         ← API (Bestellungen, CRM, Seminare)
└── deploy.py            ← nur Kunden-Stack — Agency später eigenes Script
```

---

## Statisches Backup

Falls Replit mal weg ist:

```bash
python scripts/download_agency_static.py
```

Speichert Live-Build nach `agency-web/dist-backup/` — **Notfall-Kopie**, kein Ersatz für Quellcode.

---

## Nächster Schritt für dich

**Replit-ZIP downloaden und nach `agency-web/` legen** — dann sag Bescheid, ich richte Deploy und erste Anpassungen ein.
