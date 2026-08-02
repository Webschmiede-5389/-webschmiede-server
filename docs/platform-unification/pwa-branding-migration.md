# PWA Branding Migration (CRM)

| Item | Vorher | Nachher |
|------|--------|---------|
| Manifest name | Webschmiede CRM | WebSchmiede CRM |
| Icons | `/static/icons/icon-*.png` | `/static/ws/brand/webschmiede/app-icon-*.png` |
| Favicon | icons | `/static/ws/brand/webschmiede/favicon.png` |
| theme_color | `#FF6600` | `#FF6600` (unverändert) |
| SW cache | `ws-crm-v1` | `ws-crm-v3-pilot` |
| Manifest query | — | `?v=pilot3` |

Offline-Geschäftslogik unverändert (nur Shell-Precache-Pfade). Alte Cache-Keys werden in `activate` gelöscht.

**Rollback:** Manifest/SW/Favicon-Links zurück auf `/static/icons/`; Cache-Name bump erneut.
