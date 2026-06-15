$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$EnvFile = Join-Path $Root ".env.ps1"
if (Test-Path $EnvFile) {
    . $EnvFile
}

if (-not $env:SECRET_KEY) {
    throw "SECRET_KEY is not set. Create .env.ps1 before starting the service."
}

& "$Root\.venv\Scripts\python.exe" -m waitress --listen=0.0.0.0:8000 wsgi:app
