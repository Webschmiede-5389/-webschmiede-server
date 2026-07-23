# Requesty in Cursor – nur bei Limit

Stand: 2026-07-22

**Normal:** Cursor-Abo (kein Requesty, kein Router).  
**Bei Limit:** Fallback manuell einschalten → Auto-Wahl A/B/C über Requesty EU.

## Bei Cursor-Limit

```powershell
cd C:\Users\kumex\OneDrive\Desktop\Jarvis\Server
.\scripts\enable_requesty_cursor_fallback.ps1
```

Oder: `python scripts/requesty_cursor_fallback.py enable`

Dann:

1. Cursor **Reload Window**
2. Models → `requesty-auto` hinzufügen und wählen

## Zurück zum Cursor-Abo

```powershell
.\scripts\disable_requesty_cursor_fallback.ps1
```

Status: `python scripts/requesty_cursor_fallback.py status`

## Routen (nur im Fallback aktiv)

| Route | Wann | Modell |
|-------|------|--------|
| A | kurze Fragen | Mistral small → GPT-4o-mini |
| B | Code/Agent | Claude Sonnet → GPT-4o-mini |
| C | Vision | GPT-4o-mini |

Ketten: `requesty.secrets.local` → `CURSOR_ROUTE_A/B/C`

## Hinweis

Es gibt **keinen** Autostart. Requesty läuft erst, wenn du `enable_…` startest.
