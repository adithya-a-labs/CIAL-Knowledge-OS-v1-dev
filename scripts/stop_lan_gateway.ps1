[CmdletBinding()]
param(
    [ValidateRange(1, 120)]
    [int]$TimeoutSeconds = 15
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$LanRoot = Join-Path $RepoRoot "outputs\lan-server"
$LockPath = Join-Path $LanRoot "manager.lock"
$GuardPath = "$LockPath.guard"
$StopPath = Join-Path $LanRoot "stop.request"
$CaddyPidPath = Join-Path $LanRoot "caddy.pid.json"
$GeneratedCaddyfile = Join-Path $LanRoot "Caddyfile.generated"
$StatusPath = Join-Path $LanRoot "status.json"

function Get-RecordedPid {
    param([string]$Path, [string]$Property = "pid")
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    try {
        $raw = [System.IO.File]::ReadAllText($Path).Trim()
        if ($raw.StartsWith("{")) { return [int](($raw | ConvertFrom-Json).$Property) }
        return [int]$raw
    } catch { return $null }
}

function Get-ProcessRecord {
    param([int]$ProcessId)
    if ($ProcessId -le 0) { return $null }
    try {
        return Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction Stop
    } catch { return $null }
}

function Test-CialManagerProcess {
    param([int]$ProcessId)
    $process = Get-ProcessRecord -ProcessId $ProcessId
    return $null -ne $process -and
        [string]$process.CommandLine -match "backend\.app\.lan\.manager"
}

function Test-ManagerLockActive {
    if (-not (Test-Path -LiteralPath $GuardPath -PathType Leaf)) { return $false }
    $stream = $null
    try {
        $stream = [System.IO.File]::Open($GuardPath, "Open", "ReadWrite", "ReadWrite")
        $stream.Lock(0, 1)
        $stream.Unlock(0, 1)
        return $false
    } catch { return $true }
    finally {
        if ($null -ne $stream) { $stream.Dispose() }
    }
}

function Stop-OwnedCaddy {
    if (-not (Test-Path -LiteralPath $CaddyPidPath -PathType Leaf)) { return }
    try {
        $metadata = Get-Content -Raw -LiteralPath $CaddyPidPath | ConvertFrom-Json
        $caddyPid = [int]$metadata.pid
        $process = Get-ProcessRecord -ProcessId $caddyPid
        if ($null -eq $process) {
            Remove-Item -LiteralPath $CaddyPidPath -Force
            return
        }
        $command = [string]$process.CommandLine
        $isOwned = [string]$process.Name -match "^caddy(\.exe)?$" -and
            $command -match [regex]::Escape($GeneratedCaddyfile)
        if (-not $isOwned) {
            Write-Warning "Recorded Caddy PID does not match the CIAL-owned gateway; it was not stopped."
            return
        }
        Stop-Process -Id $caddyPid -Force -ErrorAction Stop
        Remove-Item -LiteralPath $CaddyPidPath -Force
    } catch {
        Write-Warning "Unable to verify or stop the CIAL-owned Caddy process."
    }
}

function Remove-StaleLock {
    if (
        -not (Test-Path -LiteralPath $LockPath -PathType Leaf) -and
        -not (Test-Path -LiteralPath $GuardPath -PathType Leaf)
    ) { return }
    $stream = $null
    try {
        $stream = [System.IO.File]::Open($GuardPath, "OpenOrCreate", "ReadWrite", "ReadWrite")
        $stream.Lock(0, 1)
        $stream.Unlock(0, 1)
        $stream.Dispose()
        $stream = $null
        Remove-Item -LiteralPath $LockPath -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $GuardPath -Force -ErrorAction SilentlyContinue
    } catch {
        # A live manager still owns the byte-range lock.
    } finally {
        if ($null -ne $stream) { $stream.Dispose() }
    }
}

function Write-StoppedStatus {
    $status = [ordered]@{
        state = "stopped"
        enabled = $true
        mode = "hotspot"
        gateway_ready = $false
        discovery_ready = $false
        hostname = $null
        scheme = "http"
        port = $null
        hotspot_detected = $false
        bind_address_available = $false
        ip_fallback_available = $false
        tls_state = "unconfigured"
        firewall_state = "unmanaged"
        keep_awake = $false
        checked_at = [DateTime]::UtcNow.ToString("o")
        safe_detail = "LAN access is stopped. Local CIAL remains available."
        ip_fallback_url = $null
        domain_url = $null
    }
    $json = $status | ConvertTo-Json
    [System.IO.File]::WriteAllText(
        $StatusPath,
        $json,
        [System.Text.UTF8Encoding]::new($false)
    )
}

New-Item -ItemType Directory -Force -Path $LanRoot | Out-Null
$managerPid = Get-RecordedPid -Path $LockPath
$managerOwned = $null -ne $managerPid -and (Test-CialManagerProcess -ProcessId $managerPid)
[System.IO.File]::WriteAllText($StopPath, "stop")

if (Test-ManagerLockActive) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        Start-Sleep -Milliseconds 250
        if (-not (Test-ManagerLockActive)) { break }
    } while ((Get-Date) -lt $deadline)

    if (Test-ManagerLockActive) {
        if (-not $managerOwned) {
            throw "The LAN manager lock is active but its owner could not be verified. No process was killed."
        }
        Stop-Process -Id $managerPid -Force -ErrorAction Stop
        Write-Warning "The owned LAN manager did not stop gracefully and was terminated."
        Start-Sleep -Milliseconds 500
        if (Test-ManagerLockActive) {
            throw "The owned LAN manager did not release its lock after termination."
        }
    }
}

Stop-OwnedCaddy
Remove-StaleLock

$ownedRules = @(Get-NetFirewallRule -Group "CIAL Knowledge OS LAN" -ErrorAction SilentlyContinue)
if ($ownedRules.Count -gt 0) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "lan_firewall.ps1") -Mode Remove | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "CIAL-owned firewall rules could not be removed; run this stop command as Administrator."
    }
}

Remove-Item -LiteralPath $StopPath -Force -ErrorAction SilentlyContinue
Write-StoppedStatus
Write-Host "CIAL LAN gateway is stopped."
exit 0
