param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [string]$QdrantUrl = "http://localhost:6335",
    [switch]$NoBrowser
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
New-Item -ItemType Directory -Force -Path $LogsRoot | Out-Null
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
        [scriptblock]$Predicate = $null
    )
    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 5
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

function Get-EnvMap {
    param([string[]]$Paths)
    $map = @{}
    foreach ($path in $Paths) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { continue }
        foreach ($line in Get-Content -LiteralPath $path) {
            $trimmed = $line.Trim()
            if ([string]::IsNullOrWhiteSpace($trimmed) -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) { continue }
            $parts = $trimmed.Split("=", 2)
            $value = $parts[1].Trim()
            if ($value.Length -ge 2 -and (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'")))) {
                $value = $value.Substring(1, $value.Length - 2)
            }
            $map[$parts[0].Trim()] = $value
        }
    }
    return $map
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
    $envMap = Get-EnvMap -Paths @((Join-Path $RepoRoot ".env"), (Join-Path $BackendRoot ".env"), (Join-Path $BackendRoot "backend\.env"))
    $databaseUrl = $envMap["DATABASE_URL"]
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
    if (Wait-Url -Url "$QdrantUrl/collections" -Seconds 5) {
        Write-Host "Qdrant is already ready at $QdrantUrl."
        return
    }
    if (-not (Test-Path -LiteralPath $QdrantComposeFile -PathType Leaf)) {
        Stop-Launch "Missing Qdrant compose file: $QdrantComposeFile"
    }
    Ensure-Docker
    & docker.exe compose -f $QdrantComposeFile up -d
    if ($LASTEXITCODE -ne 0) { Stop-Launch "Qdrant compose startup failed." }
    if (-not (Wait-Url -Url "$QdrantUrl/collections" -Seconds 90)) {
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

function Invoke-DatabaseMigrations {
    Write-Step "Applying metadata database migrations"
    $previousPythonPath = $env:PYTHONPATH
    $env:PYTHONPATH = "$BackendRoot;$BackendRoot\src"
    Push-Location $BackendRoot
    try {
        & $PythonExe -m alembic upgrade head
        if ($LASTEXITCODE -ne 0) { Stop-Launch "Alembic upgrade failed." }
    }
    finally {
        Pop-Location
        $env:PYTHONPATH = $previousPythonPath
    }
}

function Start-Backend {
    Write-Step "Checking backend"
    if (Wait-Url -Url "http://127.0.0.1:$BackendPort/api/health" -Seconds 5) {
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
    Start-Process -FilePath $PythonExe -ArgumentList @("-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "$BackendPort") -WorkingDirectory $BackendRoot -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err | Out-Null
    $env:PYTHONPATH = $previousPythonPath
    if (-not (Wait-Url -Url "http://127.0.0.1:$BackendPort/api/health" -Seconds 180)) {
        Stop-Launch "Backend did not become reachable. See $out and $err."
    }
    $ready = Wait-Url -Url "http://127.0.0.1:$BackendPort/api/health" -Seconds 300 -Predicate { param($body) $body.api_ready -eq $true }
    if (-not $ready) {
        Stop-Launch "Backend reached HTTP health but API readiness failed. Check backend startup logs."
    }
}

function Start-Indexer {
    Write-Step "Checking standalone indexer"
    if (Wait-Url -Url "http://127.0.0.1:$BackendPort/api/health" -Seconds 5 -Predicate { param($body) $body.indexer_seen -eq $true }) {
        Write-Host "A fresh standalone indexer heartbeat already exists."
        return
    }
    $out = Join-Path $LogsRoot "indexer-$Timestamp.out.log"
    $err = Join-Path $LogsRoot "indexer-$Timestamp.err.log"
    $previousPythonPath = $env:PYTHONPATH
    $env:PYTHONPATH = "$BackendRoot;$BackendRoot\src"
    Start-Process -FilePath $PythonExe -ArgumentList @("backend\indexer_main.py") -WorkingDirectory $BackendRoot -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err | Out-Null
    $env:PYTHONPATH = $previousPythonPath
    if (-not (Wait-Url -Url "http://127.0.0.1:$BackendPort/api/health" -Seconds 300 -Predicate { param($body) $body.indexer_seen -eq $true })) {
        Stop-Launch "The standalone indexer did not publish a heartbeat. See $out and $err."
    }
}

function Start-Frontend {
    Write-Step "Checking frontend"
    if (Wait-Url -Url "http://127.0.0.1:$FrontendPort" -Seconds 5) {
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
    $env:PORT = "$FrontendPort"
    $env:VITE_API_BASE_URL = "http://127.0.0.1:$BackendPort"
    Start-Process -FilePath $vite -ArgumentList @("preview", "--host", "127.0.0.1") -WorkingDirectory $FrontendRoot -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err | Out-Null
    $env:PORT = $previousPort
    $env:VITE_API_BASE_URL = $previousApiBaseUrl
    if (-not (Wait-Url -Url "http://127.0.0.1:$FrontendPort" -Seconds 90)) {
        Stop-Launch "Frontend did not become reachable. See $out and $err."
    }
}

function Confirm-ApplicationStable {
    Write-Step "Confirming application readiness"
    Start-Sleep -Seconds 3
    if (-not (Wait-Url -Url "http://127.0.0.1:$BackendPort/api/health" -Seconds 10 -Predicate { param($body) $body.api_ready -eq $true -and $body.indexer_seen -eq $true })) {
        Stop-Launch "Backend readiness was not stable after startup."
    }
    if (-not (Wait-Url -Url "http://127.0.0.1:$FrontendPort/login" -Seconds 10)) {
        Stop-Launch "Frontend readiness was not stable after startup."
    }
}

try {
    Assert-ApplicationFiles
    Assert-CorpusConfiguration
    Ensure-Postgres
    Ensure-Qdrant
    Ensure-Ollama
    Invoke-DatabaseMigrations
    Start-Backend
    Start-Indexer
    Start-Frontend
    Confirm-ApplicationStable
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
