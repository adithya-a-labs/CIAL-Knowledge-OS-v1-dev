param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Activate = Join-Path $Root ".venv\Scripts\Activate.ps1"
$ServiceRoot = Join-Path $Root "services\knowledge-engine"

if (-not (Test-Path -LiteralPath $Activate)) {
    Write-Host "Missing .venv. Create it with: py -3.11 -m venv .venv" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path -LiteralPath (Join-Path $ServiceRoot "backend\app\main.py"))) {
    Write-Host "Missing service backend at services\knowledge-engine\backend\app." -ForegroundColor Red
    exit 1
}

. $Activate
Set-Location -LiteralPath $ServiceRoot

Write-Host "Starting CIAL Knowledge OS backend on http://127.0.0.1:$Port"
Write-Host "Backend source: services\knowledge-engine\backend\app"
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port $Port
exit $LASTEXITCODE
