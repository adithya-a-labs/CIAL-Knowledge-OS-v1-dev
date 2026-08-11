param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Activate = Join-Path $Root ".venv\Scripts\Activate.ps1"
$ServiceRoot = Join-Path $Root "services\knowledge-engine"

. (Join-Path $PSScriptRoot "runtime_env.ps1")

if (-not (Test-Path -LiteralPath $Activate)) {
    Write-Host "Missing .venv. Create it with: py -3.11 -m venv .venv" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path -LiteralPath (Join-Path $ServiceRoot "backend\app\main.py"))) {
    Write-Host "Missing service backend at services\knowledge-engine\backend\app." -ForegroundColor Red
    exit 1
}

Import-CialRuntimeEnvironment -RepoRoot $Root -RequiredKeys @(
    "DATABASE_URL",
    "CIAL_QDRANT_API_KEY"
) | Out-Null
Clear-CialMigrationCredential
. $Activate
Set-Location -LiteralPath $ServiceRoot

Write-Host "Starting CIAL Knowledge OS backend on http://127.0.0.1:$Port"
Write-Host "Backend source: services\knowledge-engine\backend\app"
Write-Host "Corpus indexing is handled by scripts\start_indexer.ps1."
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port $Port
exit $LASTEXITCODE
