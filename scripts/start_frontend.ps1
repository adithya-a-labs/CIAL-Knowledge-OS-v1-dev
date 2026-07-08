$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$FrontendRoot = Join-Path $Root "frontend"

if (-not (Test-Path -LiteralPath $FrontendRoot)) {
    Write-Host "Missing frontend directory." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path -LiteralPath (Join-Path $FrontendRoot "node_modules"))) {
    Write-Host "Missing frontend dependencies. Run: cd frontend && pnpm install" -ForegroundColor Red
    exit 1
}

Set-Location -LiteralPath $FrontendRoot
Write-Host "Starting CIAL Knowledge OS frontend."
pnpm run dev
exit $LASTEXITCODE
