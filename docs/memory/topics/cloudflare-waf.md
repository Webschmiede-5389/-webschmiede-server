# Cloudflare WAF / Proxy

Stand: 2026-07-17

## Beschluss

Agency und alle neuen Kunden-Domains hinter Cloudflare (orange Proxy), Schutzniveau vergleichbar mit GHL: DDoS, Bot, HTTPS-Zwang, Security Level.

## Stand Agency

- Zone + A-Records (proxied) + Schutzprofil gesetzt
- Nginx Real-IP live
- Status noch `pending` bis NS bei IONOS

NS: `phil.ns.cloudflare.com`, `vera.ns.cloudflare.com`

## Kunden

INWX-Kauf → CF-Zone → proxied A → Schutzprofil → NS bei INWX auf CF.

Skript: `scripts/activate_agency_cloudflare_waf.py`, `scripts/provision_domain_inwx.py`
Modul: `integrations/cloudflare_protect.py`

## Nächster Schritt

Christian stellt Agency-NS bei IONOS um. Danach Zone Active prüfen.
