# Topic: SHY001 Domain snackhouse-yassine.de

Stand: 2026-07-17

## Domain

`snackhouse-yassine.de` (korrekt mit Doppel-s)

## Erledigt

- Cloudflare-Zone angelegt (pending)
- A `@` + `www` → web-01neu `167.233.150.230` (Proxy an)
- Nginx vhost auf web-01neu (HTTP)
- `kunden/SHY001_snackhouse.json` → selected / pending_purchase

## Nameserver (nach Kauf bei IONOS)

- `phil.ns.cloudflare.com`
- `vera.ns.cloudflare.com`

## Christian

**Kauf-Freigabe:** 2026-07-17 („kauf die Domain“)

**Blocker:** Cloudflare Registrar kann `.de` nicht (`extension_not_supported`). Kein IONOS/INWX-API-Key in Secrets.

1. Domain bei IONOS kaufen: https://www.ionos.de/domain-kaufen?q=snackhouse-yassine.de
2. Nameserver auf Cloudflare setzen:
   - `phil.ns.cloudflare.com`
   - `vera.ns.cloudflare.com`
3. Dann: `python scripts/setup_shy001_domain.py snackhouse-yassine.de --ssl`

Optional (automatisch kaufbar): `snackhouse-yassine.com` ~10 USD über Cloudflare — nur wenn Christian das will statt `.de`.

## Parallel

Subdomain `yassine.digitalehandwerkskunst.de` bleibt erreichbar.
