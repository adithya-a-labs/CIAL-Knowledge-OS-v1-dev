[CmdletBinding()]
param(
    [int]$BackendPort = 8000,
    [switch]$DryRun,
    [ValidateSet("127.0.0.1")]
    [string]$TestBind,
    [string]$FrontendRoot
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$PythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    throw "Missing Python environment. Run Install-CIAL-Knowledge-OS.bat first."
}

$env:CIAL_LAN_ACCESS_ENABLED = "true"
$env:PYTHONPATH = "$(Join-Path $RepoRoot 'services\knowledge-engine');$(Join-Path $RepoRoot 'services\knowledge-engine\src')"
$arguments = @("-m", "backend.app.lan.manager", "--backend-port", "$BackendPort")
if ($DryRun) { $arguments += "--dry-run" }
if ($TestBind) { $arguments += @("--test-bind", $TestBind) }
if ($FrontendRoot) { $arguments += @("--frontend-root", $FrontendRoot) }

do {
    & $PythonExe @arguments
    $managerExitCode = $LASTEXITCODE
    if ($managerExitCode -eq 75) {
        Start-Sleep -Seconds 1
    }
} while ($managerExitCode -eq 75)

exit $managerExitCode
