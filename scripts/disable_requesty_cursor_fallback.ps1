# Requesty aus, zurueck zu Cursor-Abo
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
python scripts\requesty_cursor_fallback.py disable
