# Bei Cursor-Limit: Requesty einschalten
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
python scripts\requesty_cursor_fallback.py enable
