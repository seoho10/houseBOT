# houseBOT daily summary runner (called by Windows Task Scheduler)
# Locates the project from this script's directory, loads .env, then runs python module.
$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectDir

if (-not (Test-Path ".env")) {
    Write-Error ".env not found in $ProjectDir"
    exit 1
}

Get-Content ".env" | ForEach-Object {
    if ($_ -match "^([A-Z_][A-Z0-9_]*)=(.*)$") {
        Set-Item -Path "env:$($matches[1])" -Value $matches[2]
    }
}

$env:PYTHONIOENCODING = "utf-8"
python -m src.run_daily
exit $LASTEXITCODE
