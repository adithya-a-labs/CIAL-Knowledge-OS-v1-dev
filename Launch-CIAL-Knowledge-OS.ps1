param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [string]$QdrantUrl = "http://localhost:6335",
    [switch]$NoBrowser,
    [switch]$Lan,
    [switch]$RebuildLanFrontend,
    [switch]$LanDryRun
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$RepoRoot = $PSScriptRoot
$BackendRoot = Join-Path $RepoRoot "services\knowledge-engine"
$FrontendRoot = Join-Path $RepoRoot "frontend"
$PythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$AppConfigPath = Join-Path $RepoRoot "data\config\application.json"
$QdrantComposeFile = Join-Path $BackendRoot "docker-compose.qdrant.yml"
$LogsRoot = Join-Path $RepoRoot "outputs\launcher\logs"
$StateRoot = Join-Path $RepoRoot "outputs\launcher\runtime"
$MigrationEnvPath = Join-Path $RepoRoot "outputs\installer\runtime\migration.env"
$RuntimeEnvScript = Join-Path $RepoRoot "scripts\runtime_env.ps1"
. $RuntimeEnvScript
New-Item -ItemType Directory -Force -Path $LogsRoot, $StateRoot | Out-Null
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$LogPath = Join-Path $LogsRoot "launch-$Timestamp.log"
Start-Transcript -Path $LogPath -Append | Out-Null

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "== $Message ==" -ForegroundColor Cyan
}

function Stop-Launch {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Red
    throw $Message
}

function Get-CommandPath {
    param([string]$Name)
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -eq $command) { return $null }
    return $command.Source
}

function Test-PortOpen {
    param([string]$HostName, [int]$Port)
    try {
        $client = [System.Net.Sockets.TcpClient]::new()
        $async = $client.BeginConnect($HostName, $Port, $null, $null)
        $success = $async.AsyncWaitHandle.WaitOne(1000, $false)
        if ($success) { $client.EndConnect($async) }
        $client.Close()
        return $success
    }
    catch {
        return $false
    }
}

function Wait-Url {
    param(
        [string]$Url,
        [int]$Seconds = 120,
        [scriptblock]$Predicate = $null,
        [hashtable]$Headers = @{}
    )
    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 5 -Headers $Headers
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                if ($null -eq $Predicate) { return $true }
                $json = $response.Content | ConvertFrom-Json
                if (& $Predicate $json) { return $true }
            }
        }
        catch {
            Start-Sleep -Seconds 2
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)
    return $false
}

function Get-PortProcessId {
    param([int]$Port)
    $lines = netstat -ano | Select-String ":$Port\s"
    foreach ($line in $lines) {
        $parts = ($line.Line -split "\s+") | Where-Object { $_ }
        if ($parts.Length -ge 5 -and $parts[1] -match ":$Port$" -and $parts[3] -eq "LISTENING") {
            return [int]$parts[-1]
        }
    }
    return $null
}

function Assert-ApplicationFiles {
    Write-Step "Checking installed files"
    if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
        Stop-Launch "Missing Python virtual environment. Run Install-CIAL-Knowledge-OS.bat first."
    }
    if (-not (Test-Path -LiteralPath (Join-Path $FrontendRoot "dist\public\index.html") -PathType Leaf)) {
        Stop-Launch "Missing frontend production build. Run Install-CIAL-Knowledge-OS.bat first."
    }
    if (-not (Test-Path -LiteralPath (Join-Path $FrontendRoot "node_modules") -PathType Container)) {
        Stop-Launch "Missing frontend node_modules. Run Install-CIAL-Knowledge-OS.bat first."
    }
}

function Assert-CorpusConfiguration {
    Write-Step "Checking enterprise repository configuration"
    if (-not (Test-Path -LiteralPath $AppConfigPath -PathType Leaf)) {
        Stop-Launch "Application config is missing: $AppConfigPath. Run Install-CIAL-Knowledge-OS.bat and select the enterprise repository."
    }
    $config = Get-Content -LiteralPath $AppConfigPath -Raw | ConvertFrom-Json
    $repo = @($config.repositories | Where-Object { $_.id -eq "enterprise" -and $_.enabled -ne $false } | Select-Object -First 1)
    if ($repo.Count -eq 0 -or [string]::IsNullOrWhiteSpace($repo[0].path)) {
        Stop-Launch "Enterprise repository is not configured in $AppConfigPath."
    }
    if (-not (Test-Path -LiteralPath $repo[0].path -PathType Container)) {
        Stop-Launch "Configured enterprise repository does not exist or is inaccessible: $($repo[0].path)"
    }
    try {
        Get-ChildItem -LiteralPath $repo[0].path -Force -ErrorAction Stop | Select-Object -First 1 | Out-Null
    }
    catch {
        Stop-Launch "Configured enterprise repository is not readable: $($repo[0].path)"
    }
    Write-Host "Repository: $($repo[0].path)"
}

function Ensure-Docker {
    Write-Step "Checking Docker"
    $docker = Get-CommandPath "docker.exe"
    if ($null -eq $docker) { Stop-Launch "Docker CLI was not found. Run the installer or start Docker Desktop." }
    & $docker info | Out-Null
    if ($LASTEXITCODE -eq 0) {
        return
    }
    $dockerDesktop = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
    if (Test-Path -LiteralPath $dockerDesktop) {
        Start-Process -FilePath $dockerDesktop -WindowStyle Hidden
    }
    $deadline = (Get-Date).AddMinutes(3)
    do {
        Start-Sleep -Seconds 5
        & $docker info | Out-Null
        if ($LASTEXITCODE -eq 0) {
            return
        }
    } while ((Get-Date) -lt $deadline)
    Stop-Launch "Docker Desktop is not ready."
}

function Ensure-Postgres {
    Write-Step "Checking PostgreSQL"
    $databaseUrl = $env:DATABASE_URL
    if ([string]::IsNullOrWhiteSpace($databaseUrl)) {
        Stop-Launch "DATABASE_URL is not configured in backend environment."
    }
    if ($databaseUrl -match "@([^:/]+):(\d+)/") {
        $hostName = $Matches[1]
        $port = [int]$Matches[2]
        if (Test-PortOpen -HostName $hostName -Port $port) {
            Write-Host "PostgreSQL reachable at ${hostName}:$port."
            return
        }
    }
    $containerName = "cial-knowledge-os-v1-dev-postgres"
    $docker = Get-CommandPath "docker.exe"
    $exists = (& $docker ps -a --format "{{.Names}}") -contains $containerName
    if ($exists) {
        Ensure-Docker
        & $docker start $containerName | Out-Null
        Start-Sleep -Seconds 5
        if ($databaseUrl -match "@([^:/]+):(\d+)/" -and (Test-PortOpen -HostName $Matches[1] -Port ([int]$Matches[2]))) {
            return
        }
    }
    Stop-Launch "PostgreSQL is not reachable and no healthy installer-managed container could be started."
}

function Ensure-Qdrant {
    Write-Step "Checking Qdrant"
    if ([string]::IsNullOrWhiteSpace($env:CIAL_QDRANT_API_KEY)) { Stop-Launch "CIAL_QDRANT_API_KEY is missing." }
    $qdrantHeaders = @{ "api-key" = $env:CIAL_QDRANT_API_KEY }
    if (Wait-Url -Url "$QdrantUrl/collections" -Seconds 5 -Headers $qdrantHeaders) {
        Write-Host "Qdrant is already ready at $QdrantUrl."
        return
    }
    if (-not (Test-Path -LiteralPath $QdrantComposeFile -PathType Leaf)) {
        Stop-Launch "Missing Qdrant compose file: $QdrantComposeFile"
    }
    Ensure-Docker
    & docker.exe compose -f $QdrantComposeFile up -d
    if ($LASTEXITCODE -ne 0) { Stop-Launch "Qdrant compose startup failed." }
    if (-not (Wait-Url -Url "$QdrantUrl/collections" -Seconds 90 -Headers $qdrantHeaders)) {
        Stop-Launch "Qdrant did not become ready at $QdrantUrl."
    }
}

function Ensure-Ollama {
    Write-Step "Checking Ollama"
    if (Wait-Url -Url "http://127.0.0.1:11434/api/tags" -Seconds 5) {
        return
    }
    $ollama = Get-CommandPath "ollama.exe"
    if ($null -eq $ollama) { Stop-Launch "Ollama executable was not found." }
    Start-Process -FilePath $ollama -ArgumentList "serve" -WindowStyle Hidden
    if (-not (Wait-Url -Url "http://127.0.0.1:11434/api/tags" -Seconds 90)) {
        Stop-Launch "Ollama did not become ready."
    }
}

function Assert-OwnedListener {
    param([int]$Port, [string]$ExpectedExecutable, [string]$CommandPattern)
    $processId = Get-PortProcessId -Port $Port
    if ($null -eq $processId) { return $false }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction Stop
    $actualExecutable = [System.IO.Path]::GetFullPath([string]$process.ExecutablePath)
    $expected = [System.IO.Path]::GetFullPath($ExpectedExecutable)
    if ($actualExecutable -ne $expected -or [string]$process.CommandLine -notmatch $CommandPattern) {
        Stop-Launch "Port $Port is occupied by an unexpected process; service reuse was refused."
    }
    $owner = Invoke-CimMethod -InputObject $process -MethodName GetOwner
    if ($owner.ReturnValue -ne 0 -or $owner.User -ne [Environment]::UserName) {
        Stop-Launch "Port $Port listener is not owned by the current CIAL operator."
    }
    return $true
}

function Assert-LanFrontendBundle {
    if (-not $Lan) { return }
    Write-Step "Verifying same-origin LAN frontend bundle"
    if ($RebuildLanFrontend) {
        $previousApiBase = $env:VITE_API_BASE_URL
        $env:VITE_API_BASE_URL = ""
        Push-Location $FrontendRoot
        try {
            & pnpm.cmd run build
            if ($LASTEXITCODE -ne 0) { Stop-Launch "LAN frontend production build failed." }
        }
        finally {
            Pop-Location
            $env:VITE_API_BASE_URL = $previousApiBase
        }
    }
    $assets = Get-ChildItem -LiteralPath (Join-Path $FrontendRoot "dist\public\assets") -Filter "*.js" -File -ErrorAction Stop
    $forbidden = "http://localhost:8000|http://127\.0\.0\.1:8000|:6335|:11434|:5432|:5173"
    $match = $assets | Select-String -Pattern $forbidden -List
    if ($match) {
        Stop-Launch "The production bundle contains an internal service target. Rerun with --lan -RebuildLanFrontend after stopping any process holding frontend\dist."
    }
    Write-Host "Production bundle uses the same-origin API contract."
}

function Invoke-DatabaseMigrations {
    Write-Step "Applying metadata database migrations"
    $previousPythonPath = $env:PYTHONPATH
    $env:CIAL_MIGRATION_DATABASE_URL = Get-CialScopedEnvironmentValue `
        -Name "CIAL_MIGRATION_DATABASE_URL" `
        -ProtectedPath $MigrationEnvPath
    $env:PYTHONPATH = "$BackendRoot;$BackendRoot\src"
    Push-Location $BackendRoot
    try {
        & $PythonExe -m alembic upgrade head
        if ($LASTEXITCODE -ne 0) { Stop-Launch "Alembic upgrade failed." }
    }
    finally {
        Pop-Location
        $env:PYTHONPATH = $previousPythonPath
        Clear-CialMigrationCredential
    }
}

function Start-Backend {
    Write-Step "Checking backend"
    if (Wait-Url -Url "http://127.0.0.1:$BackendPort/api/health" -Seconds 5) {
        [void](Assert-OwnedListener -Port $BackendPort -ExpectedExecutable $PythonExe -CommandPattern "backend\.app\.main:app")
        Write-Host "Backend already responds on port $BackendPort."
        return
    }
    $portProcessId = Get-PortProcessId -Port $BackendPort
    if ($null -ne $portProcessId) {
        Stop-Launch "Port $BackendPort is already occupied by process $portProcessId, but it is not the CIAL backend."
    }
    $out = Join-Path $LogsRoot "backend-$Timestamp.out.log"
    $err = Join-Path $LogsRoot "backend-$Timestamp.err.log"
    $previousPythonPath = $env:PYTHONPATH
    $env:PYTHONPATH = "$BackendRoot;$BackendRoot\src"
    Start-Process -FilePath $PythonExe -ArgumentList @("-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "$BackendPort", "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1") -WorkingDirectory $BackendRoot -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err | Out-Null
    $env:PYTHONPATH = $previousPythonPath
    if (-not (Wait-Url -Url "http://127.0.0.1:$BackendPort/api/health" -Seconds 180)) {
        Stop-Launch "Backend did not become reachable. See $out and $err."
    }
    [void](Assert-OwnedListener -Port $BackendPort -ExpectedExecutable $PythonExe -CommandPattern "backend\.app\.main:app")
}

function Start-LanGateway {
    if (-not $Lan) { return }
    Write-Step "Starting optional Laptop LAN Server Mode"
    $httpsEnabled = if (-not [string]::IsNullOrWhiteSpace($env:CIAL_LAN_HTTPS_ENABLED)) {
        $env:CIAL_LAN_HTTPS_ENABLED
    } else { "true" }
    if ($httpsEnabled -notmatch "^(1|true|yes|on)$") {
        Stop-Launch "LAN mode requires HTTPS. Set CIAL_LAN_HTTPS_ENABLED=true and provision the gateway certificate."
    }
    $env:CIAL_LAN_ACCESS_ENABLED = "true"
    $env:CIAL_LAN_HTTPS_ENABLED = "true"
    $env:CIAL_AUTH_COOKIE_SECURE = "true"
    $script = Join-Path $RepoRoot "scripts\start_lan_gateway.ps1"
    $out = Join-Path $LogsRoot "lan-manager-$Timestamp.out.log"
    $err = Join-Path $LogsRoot "lan-manager-$Timestamp.err.log"
    $arguments = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $script, "-BackendPort", "$BackendPort")
    if ($LanDryRun) { $arguments += "-DryRun" }
    if ($LanDryRun) {
        & powershell.exe @arguments
        if ($LASTEXITCODE -ne 0) { Write-Warning "LAN dry-run failed; local CIAL remains available." }
        return
    }
    $processArguments = @($arguments)
    $processArguments[4] = '"{0}"' -f $script
    Start-Process -FilePath "powershell.exe" -ArgumentList $processArguments -WorkingDirectory $RepoRoot -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err | Out-Null
    Start-Sleep -Seconds 2
    $statusPath = Join-Path $RepoRoot "outputs\lan-server\status.json"
    if (Test-Path -LiteralPath $statusPath -PathType Leaf) {
        $lanStatus = Get-Content -Raw -LiteralPath $statusPath | ConvertFrom-Json
        Write-Host "LAN status: $($lanStatus.safe_detail)"
        if ($lanStatus.domain_url) { Write-Host "LAN domain: $($lanStatus.domain_url)" -ForegroundColor Green }
        if ($lanStatus.ip_fallback_url) { Write-Host "IP fallback: $($lanStatus.ip_fallback_url)" -ForegroundColor Green }
    }
    else {
        Write-Warning "LAN manager is starting; inspect outputs\lan-server\status.json. Local CIAL remains available."
    }
}

function Start-Indexer {
    Write-Step "Checking standalone indexer"
    $existingIndexer = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue | Where-Object {
        [System.IO.Path]::GetFullPath([string]$_.ExecutablePath) -eq [System.IO.Path]::GetFullPath($PythonExe) -and
        [string]$_.CommandLine -match "backend\\indexer_main\.py"
    } | Select-Object -First 1
    if ($null -ne $existingIndexer) {
        Write-Host "An owned standalone indexer process is already running."
        return
    }
    $out = Join-Path $LogsRoot "indexer-$Timestamp.out.log"
    $err = Join-Path $LogsRoot "indexer-$Timestamp.err.log"
    $previousPythonPath = $env:PYTHONPATH
    $env:PYTHONPATH = "$BackendRoot;$BackendRoot\src"
    $indexerProcess = Start-Process -FilePath $PythonExe -ArgumentList @("backend\indexer_main.py") -WorkingDirectory $BackendRoot -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err -PassThru
    [pscustomobject]@{ pid=$indexerProcess.Id; started_at=(Get-Date).ToString("o"); executable=$PythonExe } | ConvertTo-Json -Compress | Set-Content -LiteralPath (Join-Path $StateRoot "indexer.pid.json") -Encoding UTF8
    $env:PYTHONPATH = $previousPythonPath
    Start-Sleep -Seconds 2
    if ($indexerProcess.HasExited) { Write-Warning "The standalone indexer exited during startup. See $out and $err." }
}

function Start-Frontend {
    Write-Step "Checking frontend"
    if (Wait-Url -Url "http://127.0.0.1:$FrontendPort" -Seconds 5) {
        $nodeExecutable = (Get-Command node.exe -ErrorAction Stop).Source
        [void](Assert-OwnedListener -Port $FrontendPort -ExpectedExecutable $nodeExecutable -CommandPattern "vite")
        Write-Host "Frontend already responds on port $FrontendPort."
        return
    }
    $portProcessId = Get-PortProcessId -Port $FrontendPort
    if ($null -ne $portProcessId) {
        Stop-Launch "Port $FrontendPort is already occupied by process $portProcessId, but it is not the CIAL frontend."
    }
    $vite = Join-Path $FrontendRoot "node_modules\.bin\vite.cmd"
    if (-not (Test-Path -LiteralPath $vite -PathType Leaf)) {
        Stop-Launch "Local Vite executable was not found. Run Install-CIAL-Knowledge-OS.bat first."
    }
    $out = Join-Path $LogsRoot "frontend-$Timestamp.out.log"
    $err = Join-Path $LogsRoot "frontend-$Timestamp.err.log"
    $previousPort = $env:PORT
    $previousApiBaseUrl = $env:VITE_API_BASE_URL
    $previousApiProxyTarget = $env:API_PROXY_TARGET
    $env:PORT = "$FrontendPort"
    $env:VITE_API_BASE_URL = ""
    $env:API_PROXY_TARGET = "http://127.0.0.1:$BackendPort"
    Start-Process -FilePath $vite -ArgumentList @("preview", "--host", "127.0.0.1") -WorkingDirectory $FrontendRoot -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err | Out-Null
    $env:PORT = $previousPort
    $env:VITE_API_BASE_URL = $previousApiBaseUrl
    $env:API_PROXY_TARGET = $previousApiProxyTarget
    if (-not (Wait-Url -Url "http://127.0.0.1:$FrontendPort" -Seconds 90)) {
        Stop-Launch "Frontend did not become reachable. See $out and $err."
    }
}

function Confirm-ApplicationStable {
    Write-Step "Confirming application readiness"
    Start-Sleep -Seconds 3
    if (-not (Wait-Url -Url "http://127.0.0.1:$BackendPort/api/health" -Seconds 10)) {
        Stop-Launch "Backend liveness was not stable after startup."
    }
    if (-not (Wait-Url -Url "http://127.0.0.1:$FrontendPort/login" -Seconds 10)) {
        Stop-Launch "Frontend readiness was not stable after startup."
    }
}

try {
    Import-CialRuntimeEnvironment -RepoRoot $RepoRoot -RequiredKeys @(
        "DATABASE_URL",
        "CIAL_QDRANT_API_KEY"
    ) | Out-Null
    if ($Lan) {
        $httpsEnabled = if (-not [string]::IsNullOrWhiteSpace($env:CIAL_LAN_HTTPS_ENABLED)) {
            $env:CIAL_LAN_HTTPS_ENABLED
        } else { "true" }
        if ($httpsEnabled -notmatch "^(1|true|yes|on)$") {
            Stop-Launch "LAN mode requires HTTPS. Set CIAL_LAN_HTTPS_ENABLED=true and provision the gateway certificate."
        }
        $env:CIAL_LAN_ACCESS_ENABLED = "true"
        $env:CIAL_LAN_HTTPS_ENABLED = "true"
        $env:CIAL_AUTH_COOKIE_SECURE = "true"
    }
    Assert-ApplicationFiles
    Assert-LanFrontendBundle
    Assert-CorpusConfiguration
    Ensure-Postgres
    Ensure-Qdrant
    Ensure-Ollama
    Invoke-DatabaseMigrations
    Clear-CialMigrationCredential
    Start-Backend
    Start-Indexer
    Start-Frontend
    Confirm-ApplicationStable
    Start-LanGateway
    $url = "http://127.0.0.1:$FrontendPort/login"
    Write-Host ""
    Write-Host "CIAL Knowledge OS is ready: $url" -ForegroundColor Green
    Write-Host "Launch log: $LogPath"
    if (-not $NoBrowser) {
        Start-Process $url | Out-Null
    }
}
finally {
    Stop-Transcript | Out-Null
}
