param()

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$ServiceRoot = Join-Path $Root "services\knowledge-engine"

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    Write-Host "Missing .venv. Run the installer first." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path -LiteralPath (Join-Path $ServiceRoot "backend\indexer_main.py") -PathType Leaf)) {
    Write-Host "Missing standalone indexer entrypoint." -ForegroundColor Red
    exit 1
}

$env:PYTHONPATH = "$ServiceRoot;$ServiceRoot\src"
Set-Location -LiteralPath $ServiceRoot
Write-Host "Starting the standalone CIAL continuous indexer."
& $Python "backend\indexer_main.py"
exit $LASTEXITCODE
