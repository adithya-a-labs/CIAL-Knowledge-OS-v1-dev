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

$LanRoot = Join-Path $RepoRoot "outputs\lan-server"
$LockPath = Join-Path $LanRoot "manager.lock"
$GuardPath = "$LockPath.guard"

function Get-ManagerPid {
    if (-not (Test-Path -LiteralPath $LockPath -PathType Leaf)) { return $null }
    try {
        $raw = [System.IO.File]::ReadAllText($LockPath).Trim()
        if ($raw.StartsWith("{")) { return [int](($raw | ConvertFrom-Json).pid) }
        return [int]$raw
    } catch { return $null }
}

function Test-CialManagerProcess {
    param([int]$ProcessId)
    if ($ProcessId -le 0) { return $false }
    try {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction Stop
        return $null -ne $process -and
            [string]$process.CommandLine -match "backend\.app\.lan\.manager"
    } catch { return $false }
}

$existingPid = Get-ManagerPid
if ($null -ne $existingPid -and (Test-CialManagerProcess -ProcessId $existingPid)) {
    Write-Host "CIAL LAN manager is already running."
    exit 0
}
if (
    (Test-Path -LiteralPath $LockPath -PathType Leaf) -or
    (Test-Path -LiteralPath $GuardPath -PathType Leaf)
) {
    try {
        $stream = [System.IO.File]::Open($GuardPath, "OpenOrCreate", "ReadWrite", "ReadWrite")
        $stream.Lock(0, 1)
        $stream.Unlock(0, 1)
        $stream.Dispose()
        Remove-Item -LiteralPath $LockPath -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $GuardPath -Force -ErrorAction SilentlyContinue
        Write-Host "Recovered a stale CIAL LAN manager lock."
    } catch {
        Write-Host "CIAL LAN manager lock is active; no duplicate was started."
        exit 0
    }
}
if (Test-Path -LiteralPath (Join-Path $LanRoot "caddy.pid.json") -PathType Leaf) {
    & (Join-Path $PSScriptRoot "stop_lan_gateway.ps1") -TimeoutSeconds 1
    if ($LASTEXITCODE -ne 0) { throw "Unable to recover the previously owned LAN gateway." }
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
