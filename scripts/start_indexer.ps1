param()

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$ServiceRoot = Join-Path $Root "services\knowledge-engine"

. (Join-Path $PSScriptRoot "runtime_env.ps1")

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    Write-Host "Missing .venv. Run the installer first." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path -LiteralPath (Join-Path $ServiceRoot "backend\indexer_main.py") -PathType Leaf)) {
    Write-Host "Missing standalone indexer entrypoint." -ForegroundColor Red
    exit 1
}

Import-CialRuntimeEnvironment -RepoRoot $Root -RequiredKeys @(
    "DATABASE_URL",
    "CIAL_QDRANT_API_KEY"
) | Out-Null
Clear-CialMigrationCredential
$env:PYTHONPATH = "$ServiceRoot;$ServiceRoot\src"
Set-Location -LiteralPath $ServiceRoot
Write-Host "Starting the standalone CIAL continuous indexer."
& $Python "backend\indexer_main.py"
exit $LASTEXITCODE
