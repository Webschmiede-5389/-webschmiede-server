# Requesty Cursor-Router: Autostart einrichten / entfernen
param(
  [switch]$Remove
)

$ErrorActionPreference = "Stop"
$Startup = [Environment]::GetFolderPath("Startup")
$LinkPath = Join-Path $Startup "Webschmiede-Requesty-Cursor-Router.lnk"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Vbs = Join-Path $ScriptDir "start_requesty_cursor_router_hidden.vbs"

if ($Remove) {
  if (Test-Path $LinkPath) {
    Remove-Item $LinkPath -Force
    Write-Host "Autostart entfernt: $LinkPath"
  } else {
    Write-Host "Kein Autostart-Eintrag vorhanden."
  }
  exit 0
}

$Wsh = New-Object -ComObject WScript.Shell
$Shortcut = $Wsh.CreateShortcut($LinkPath)
$Shortcut.TargetPath = "wscript.exe"
$Shortcut.Arguments = "`"$Vbs`""
$Shortcut.WorkingDirectory = (Split-Path -Parent $ScriptDir)
$Shortcut.WindowStyle = 7
$Shortcut.Description = "Requesty Cursor Auto-Router (A/B/C)"
$Shortcut.Save()

Write-Host "Autostart gesetzt: $LinkPath"
Write-Host "Router startet unsichtbar bei Windows-Login."

$busy = Get-NetTCPConnection -LocalPort 8787 -State Listen -ErrorAction SilentlyContinue
if (-not $busy) {
  Start-Process -FilePath "wscript.exe" -ArgumentList "`"$Vbs`""
  Start-Sleep -Seconds 2
  try {
    $code = (Invoke-WebRequest -Uri "http://127.0.0.1:8787/v1/models" -UseBasicParsing -TimeoutSec 5).StatusCode
    Write-Host "Router OK (HTTP $code)"
  } catch {
    Write-Host "Router antwortet noch nicht - python/scripts pruefen."
  }
} else {
  Write-Host "Router laeuft bereits auf Port 8787."
}
