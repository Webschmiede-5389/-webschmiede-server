# DSGVO Fact-Check (belegt, kein Halluzinieren)

Stand: 2026-07-18  
Live-Snapshot: `docs/agency/dsgvo-factcheck-live.json` · `python scripts/check_dsgvo_facts.py`

## Belegte Fakten (Server)

| Fakt | Nachweis |
|------|----------|
| GHL aus | `GHL_ENABLED=false` in `.env` |
| SMS nicht live | `SMS_ENABLED=false`, `SMS_API_KEY` leer |
| WhatsApp nicht live | Access Token / Phone Number ID fehlen |
| Stripe Secret nicht gesetzt | `STRIPE_SECRET_KEY` fehlt |
| Retell-Key gesetzt | `RETELL_API_KEY` len>0 (Voice-Pfad vorhanden) |
| Web-Push technisch möglich | `VAPID_PUBLIC_KEY` + `VAPID_PRIVATE_KEY` gesetzt; UI in `order.html` |
| DocuSeal URL | `https://sign.digitalehandwerkskunst.de/` |
| Cal.com URL | `https://cal.digitalehandwerkskunst.de` |
| Nginx-Logs | `/etc/logrotate.d/nginx`: daily, **rotate 14** (nicht 7) |
| Hosting | Hetzner (Deploy-Doku, Server-Ops) |

## Texte angepasst (wegen Fakten)

| Datei | Änderung |
|-------|----------|
| `app/static/datenschutz.html` | Logs 14 Tage; Bunny/CDN ohne unbelegte Claims; Push; WA/SMS „soweit freigeschaltet“; Hetzner namentlich; Admin-Cookie statt sessionStorage |
| `agency-web/.../DatenschutzPage.tsx` | Hetzner, DocuSeal, Cal, n8n, Retell/Twilio, Stripe/seven/WA soweit; kein Umami-Snippet behauptet |
| AVV HTML/PDF/DocuSeal | Unterauftrags-Kategorien erweitert, immer „soweit eingesetzt/gebucht“ |
| `anfrage.html` | Datenschutz-Link + Pflicht-Checkbox |
| `onboarding.html` | Hinweis vor Meta-SDK |
| `nightly_watchdog.py` | Purge `message_log`/`inbox_log` nach 90 Tagen |
| `index.html` Modal | GHL/Google Fonts entfernt (bereits deployed) |

## Bewusst nicht behauptet

- Umami-Tracking live (kein Snippet auf Sites)
- SMS/WhatsApp/Stripe Endkunden-Live ohne Keys
- Cloudflare „speichert IP nicht dauerhaft“ (nicht belegt)
- Bunny „keine personenbezogenen Daten“ (IP-Übertragung bleibt)
- Server-Logs „7 Tage“ (Fakt: 14)

## Anwalt weiterhin sinnvoll

AVV/AGB vor Großkunde gegenlesen lassen. Dieses Fact-Check ersetzt keine Rechtsberatung.
