# Cloudflare Schutz (WAF / Bot) – Agency + Kunden

Stand: 2026-07-17

## Was das ist

Cloudflare sitzt **vor** dem Server (wie der Schutz hinter GHL).  
Orange Proxy = Traffic geht über Cloudflare (DDoS, Bot Fight, HTTPS-Zwang, Security Level).

## Agency jetzt

```bash
python scripts/activate_agency_cloudflare_waf.py
```

Dann **Nameserver bei IONOS** auf die ausgegebenen Cloudflare-NS umstellen  
(`phil.ns.cloudflare.com` / `vera.ns.cloudflare.com` – exakte Werte im Skript-Output).

Profil (Free-Plan):
- SSL Full, Always HTTPS, TLS 1.2+
- Security Level medium
- Browser Integrity Check
- Bot Fight Mode (wenn API erlaubt)
- Nginx Real-IP (`CF-Connecting-IP`) für echte Client-IPs / Rate-Limits

## Neue Kunden-Domains (Standard)

Kauf bei INWX + automatisch:
1. Cloudflare-Zone
2. A `@`/`www` → `WEB_HOST`, **proxied**
3. Schutzprofil
4. Nameserver bei INWX → Cloudflare

```bash
python scripts/provision_domain_inwx.py snackhouse-yassine.de --ssl
# Cloudflare ist Default (via_cloudflare=True)
# Ohne CF: später Flag --no-cloudflare (falls ergänzt)
```

Modul: `app/backend/integrations/cloudflare_protect.py`

## Hinweis Mail

MX bleibt DNS-only (nicht proxied). Agency-Mail weiter über IONOS MX in der Cloudflare-Zone.
