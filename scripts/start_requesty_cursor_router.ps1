# Requesty Cursor-Router starten (Auto-Wahl A/B/C nach Einsatzzweck)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "Starte Requesty Cursor-Router auf http://127.0.0.1:8787/v1 ..." -ForegroundColor Cyan
Write-Host "Cursor Settings → Models → Override Base URL: http://127.0.0.1:8787/v1" -ForegroundColor Yellow
Write-Host "Modell hinzufügen: requesty-auto" -ForegroundColor Yellow
Write-Host ""

python "$PSScriptRoot\requesty_cursor_router.py"
