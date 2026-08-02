# Isolated CRM full suite runner (Windows companion to .sh)
param(
  [string]$CrmRoot = "",
  [string]$OutFile = ""
)

if (-not $CrmRoot) {
  $CrmRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\crm")).Path
}
if (-not (Test-Path (Join-Path $CrmRoot "requirements.txt"))) {
  throw "CRM root invalid: $CrmRoot"
}
Set-Location $CrmRoot

$EvidenceDir = Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..")).Path "docs\platform-unification\evidence\step-4"
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
if (-not $OutFile) { $OutFile = Join-Path $EvidenceDir "full-suite-run.txt" }

$Venv = Join-Path $CrmRoot ".venv-step4"
$Py = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $Py)) {
  python -m venv $Venv
}
& $Py -m pip install -q -U pip
& $Py -m pip install -q -r requirements.txt

$sp = & $Py -c "import site; print(site.getsitepackages()[0])"
$env:PYTHONPATH = $sp

Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
Remove-Item Env:CRM_TEST_DATABASE_URL -ErrorAction SilentlyContinue
$env:APP_ENV = "test"
$env:CRM_TEST_DIALECT = "sqlite"
$env:ALLOW_CREATE_ALL = "true"
$env:CSRF_ENABLED = "false"
$env:RATE_LIMIT_ENABLED = "false"
$env:OUTBOUND_ENABLED = "false"
$env:SALES_OUTBOUND_ENABLED = "false"
$env:N8N_ENABLED = "false"
$env:NILS_WRITE_ENABLED = "false"
$env:EMAIL_SEND_ENABLED = "false"
$env:WHATSAPP_SEND_ENABLED = "false"
$env:PHONE_INTEGRATION_ENABLED = "false"
$env:PLACETEL_ENABLED = "false"
$env:PLACETEL_CLICK_TO_DIAL_ENABLED = "false"
$env:PLACETEL_WEBHOOKS_ENABLED = "false"
$env:CALL_RECORDING_ENABLED = "false"
$env:LIVE_TRANSCRIPTION_ENABLED = "false"

$commit = (& git rev-parse HEAD).Trim()
$pyver = (& $Py -c "import sys; print(sys.version.split()[0])").Trim()
$start = (Get-Date).ToUniversalTime().ToString("o")

$header = @"
=== CRM isolated full suite ===
start_utc=$start
crm_root=$CrmRoot
commit=$commit
python=$pyver
venv=$Venv
PYTHONPATH_prefix=$sp
APP_ENV=$($env:APP_ENV)
CRM_TEST_DIALECT=$($env:CRM_TEST_DIALECT)
providers=disabled
command=$Py -m pytest tests/ -q --tb=line
=== BEGIN pytest ===
"@
Set-Content -Encoding utf8 -Path $OutFile -Value $header

$stdout = "$OutFile.stdout"
$stderr = "$OutFile.stderr"
$proc = Start-Process -FilePath $Py `
  -ArgumentList @("-m", "pytest", "tests/", "-q", "--tb=line") `
  -WorkingDirectory $CrmRoot `
  -NoNewWindow -Wait -PassThru `
  -RedirectStandardOutput $stdout `
  -RedirectStandardError $stderr
if (Test-Path $stdout) { Get-Content $stdout | Add-Content -Encoding utf8 $OutFile }
if (Test-Path $stderr) { Get-Content $stderr | Add-Content -Encoding utf8 $OutFile }
Remove-Item $stdout, $stderr -ErrorAction SilentlyContinue
$code = $proc.ExitCode
$end = (Get-Date).ToUniversalTime().ToString("o")
Add-Content -Encoding utf8 $OutFile -Value @"
=== END pytest ===
exit_code=$code
end_utc=$end
"@
Write-Host "Wrote $OutFile (exit $code)"
exit $code
