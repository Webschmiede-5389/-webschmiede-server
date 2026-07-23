# Agency-Domain → Cloudflare DNS

Stand: 2026-07-17

## Modell

| Was | Wo |
|-----|-----|
| Domain-Inhaber | IONOS (lassen) |
| DNS | Cloudflare |
| Origin / Server | web-01neu `167.233.150.230` |
| Mail (MX) | weiterhin IONOS (`mx00`/`mx01.ionos.de`) |

## Zone

- Domain: `digitalehandwerkskunst.de`
- Status: `pending` bis Nameserver bei IONOS umgestellt
- Nameserver:
  - `phil.ns.cloudflare.com`
  - `vera.ns.cloudflare.com`

## Records (bereits angelegt)

- A `@`, `www`, `cal`, `yassine`, `muster`, `voice` → `167.233.150.230` (Proxy an)
- A `*` Wildcard → gleiche IP (DNS only, Free-Plan)
- MX → IONOS
- TXT SPF + Google-Verification
- SSL Mode: Full

## Christian: IONOS Nameserver

1. ionos.de → Domains → `digitalehandwerkskunst.de` → Nameserver
2. Eigene Nameserver / Cloudflare eintragen:
   - `phil.ns.cloudflare.com`
   - `vera.ns.cloudflare.com`
3. Speichern. 1–24 Std bis Cloudflare „Active“.
4. A-Records bei IONOS brauchen danach nicht mehr gepflegt zu werden.

WAF/Schutzprofil + Kunden-Standard: siehe `docs/agency/cloudflare-waf.md`  
Aktivierung: `python scripts/activate_agency_cloudflare_waf.py`

## Später Serverwechsel

Nur in Cloudflare Origin-IP ändern (einmal). Kein IONOS mehr.

## Skript

`python scripts/setup_agency_cloudflare_dns.py`
