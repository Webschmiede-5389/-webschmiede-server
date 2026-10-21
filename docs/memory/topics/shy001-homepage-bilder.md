# SHY001 – Homepage-Bilder

**Stand 2026-10-21:** Food-Fotos lagen die ganze Zeit auf Hetzner unter `/var/www/snackhouse-mechernich/img/` (`hero.jpg`, `food-*.jpg`, `hassan.jpg`). Die `index.html` zeigte fälschlich noch auf **Catbox** (GHL-Überbleibsel).

## Fix (2026-10-21)

- `app/static/index.html` → Pfade `/img/…`
- Deploy: `python scripts/shy001_index_img_paths_deploy.py` oder volles `deploy.py`
- `app/static/img/` im Repo (Sync: `python scripts/sync_shy001_img_from_server.py`)
- `deploy.py` kopiert `static/img/` → WEBROOT

## Nicht nochmal

1. **GitHub = Quelle der Wahrheit** — JPGs + HTML committen (kein „nur auf Server“).
2. **Test** — `tests/test_shy001_static_assets.py` (kein catbox in Kunden-HTML, `/img/*` vorhanden).
3. **Kein Catbox/GHL-CDN** für SHY001-Produktionsseiten.
4. Branch-Protection optional; wichtiger ist der Test vor Deploy.
