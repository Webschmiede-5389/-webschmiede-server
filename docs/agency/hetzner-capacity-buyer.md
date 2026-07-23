# Hetzner Capacity Buyer

Automatisch bestellen, sobald Kapazität da ist:

| Menge | Typ | Region |
|------:|-----|--------|
| 2 | **CX43** | Deutschland: zuerst `fsn1` (Falkenstein), sonst `nbg1` (Nürnberg) |
| 1 | **CX53** | gleich |

## Laufzeit

- Script: `scripts/hetzner_capacity_buyer.py`
- Cron (auto-01): alle **5 Minuten** → `scripts/hetzner_buyer_cron.sh`
- Log: `/var/log/hetzner-buyer.log`
- State + Root-Passwörter: `/var/lib/webschmiede/hetzner-buyer-state.json` (chmod 600)

## Befehle

```bash
# Status
python scripts/hetzner_capacity_buyer.py --status

# Nur prüfen, nichts kaufen
python scripts/hetzner_capacity_buyer.py --dry-run

# Einmal manuell (kauft wenn verfügbar)
python scripts/hetzner_capacity_buyer.py

# Cron neu installieren
python scripts/setup_hetzner_buyer.py
```

## Hinweise

- Bestehende Server (Web-01, Auto-01, Voice01, Alt) werden **nicht** mitgezählt. Es werden **zusätzlich** 2× CX43 + 1× CX53 bestellt.
- Bei Erfolg: E-Mail an `AGENCY_OWNER_EMAIL` / BCC inkl. Root-Passwort (auch in der Hetzner Console zurücksetzbar).
- Wenn alle drei Slots voll sind: Cron läuft weiter, Script beendet mit `DONE` ohne neue Käufe.
- Token: `HETZNER_API_TOKEN` in `deploy.secrets.local` / Agency Setup.
