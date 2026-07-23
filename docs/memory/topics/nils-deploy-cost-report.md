# Cursor Auto-Deploy + Tagesreport + Kosten-Wächter

Stand: 2026-07-20

## Cursor → Live

Freigabe „ja“ → Cursor Cloud Agent → fertig-Ping → Auto-Deploy (git Mirror + Sync + snack-api).
Braucht `GITHUB_TOKEN` in `cursor.secrets.local`. Flag: `NILS_CURSOR_AUTO_DEPLOY=1`.

## Tagesreport

Cron 05:30 UTC (~07:30 Berlin): Telegram + Mail.
Telegram: `tagesreport`

## Kosten

`nils_cost_sentry`: Hetzner-Buyer stoppen, Akquise-Nacht pausiert (`NILS_PAUSE_AKQUISE_AUTO=1`) bis OK.
Telegram: `kostenwächter` / `budget`
