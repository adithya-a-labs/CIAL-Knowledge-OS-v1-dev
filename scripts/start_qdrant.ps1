[CmdletBinding()]
param(
    [switch]$ShowStatus
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$ServiceRoot = Join-Path $RepoRoot "services\knowledge-engine"
$ComposeFile = Join-Path $ServiceRoot "docker-compose.qdrant.yml"

. (Join-Path $PSScriptRoot "runtime_env.ps1")

try {
    Import-CialRuntimeEnvironment -RepoRoot $RepoRoot -RequiredKeys @("CIAL_QDRANT_API_KEY") | Out-Null
    if (-not (Test-Path -LiteralPath $ComposeFile -PathType Leaf)) {
        throw "Missing Qdrant Compose file: $ComposeFile"
    }
    if (-not (Get-Command docker.exe -ErrorAction SilentlyContinue)) {
        throw "Docker CLI was not found. Install Docker Desktop and start it before running Qdrant."
    }
    & docker.exe info *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker is not running. Start Docker Desktop and try again."
    }

    Write-Host "Starting Qdrant from services\knowledge-engine\docker-compose.qdrant.yml"
    Write-Host "Qdrant host URL for this compose file: http://localhost:6335"
    & docker.exe compose -f $ComposeFile up -d
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    if ($ShowStatus) {
        & docker.exe compose -f $ComposeFile ps
        exit $LASTEXITCODE
    }
    exit 0
}
catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
