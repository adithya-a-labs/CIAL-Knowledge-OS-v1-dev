[CmdletBinding()]
param(
    [ValidateRange(1, 120)]
    [int]$TimeoutSeconds = 15
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$LanRoot = Join-Path $RepoRoot "outputs\lan-server"
$LockPath = Join-Path $LanRoot "manager.lock"
$StopPath = Join-Path $LanRoot "stop.request"
New-Item -ItemType Directory -Force -Path $LanRoot | Out-Null
[System.IO.File]::WriteAllText($StopPath, "stop")

if (-not (Test-Path -LiteralPath $LockPath -PathType Leaf)) {
    Write-Host "No CIAL LAN manager lock is present. Stop request recorded."
    exit 0
}

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
do {
    Start-Sleep -Milliseconds 250
    if (-not (Test-Path -LiteralPath $LockPath -PathType Leaf)) {
        Write-Host "CIAL LAN manager stopped cleanly."
        exit 0
    }
    try {
        $stream = [System.IO.File]::Open($LockPath, "Open", "ReadWrite", "None")
        $stream.Dispose()
        Write-Host "CIAL LAN manager stopped cleanly."
        exit 0
    } catch {
        # The manager still owns the lock.
    }
} while ((Get-Date) -lt $deadline)

throw "CIAL LAN manager did not release its lock before the timeout. No process was force-killed."
