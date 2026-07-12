param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [string]$QdrantUrl = "http://localhost:6335",
    [string]$PostgresContainerName = "cial-knowledge-os-v1-dev-postgres",
    [string]$OllamaModel = "gemma3:12b",
    [string]$EmbeddingModel = "BAAI/bge-m3",
    [string]$RerankerModel = "cross-encoder/ms-marco-MiniLM-L-6-v2",
    [switch]$NoBrowser
)

$BackendPortExplicit = $PSBoundParameters.ContainsKey("BackendPort")
$FrontendPortExplicit = $PSBoundParameters.ContainsKey("FrontendPort")
$QdrantUrlExplicit = $PSBoundParameters.ContainsKey("QdrantUrl")
$PostgresContainerExplicit = $PSBoundParameters.ContainsKey("PostgresContainerName")
$OllamaModelExplicit = $PSBoundParameters.ContainsKey("OllamaModel")
$EmbeddingModelExplicit = $PSBoundParameters.ContainsKey("EmbeddingModel")
$RerankerModelExplicit = $PSBoundParameters.ContainsKey("RerankerModel")

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$RepoRoot = $PSScriptRoot
$BackendRoot = Join-Path $RepoRoot "services\knowledge-engine"
$FrontendRoot = Join-Path $RepoRoot "frontend"
$PythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$AppConfigPath = Join-Path $RepoRoot "data\config\application.json"
$InstallStatePath = Join-Path $RepoRoot "outputs\installer\runtime\install-state.json"
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
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300) {
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

function Test-CialBackend {
    param([int]$Port, [switch]$RequireReady)
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 5
        if ($response.StatusCode -ne 200 -or -not $response.Headers["Content-Type"].StartsWith("application/json")) { return $false }
        $body = $response.Content | ConvertFrom-Json
        if ($body.service -ne "cial-knowledge-os" -or $body.application_version -ne "0.1.0" -or $body.phase -ne "4.5" -or $body.database_ready -ne $true) { return $false }
        if ($body.repository_id -ne $script:ExpectedRepositoryId -or $body.qdrant_url.TrimEnd('/') -ne $QdrantUrl.TrimEnd('/') -or $body.ollama_model -ne $OllamaModel -or $body.embedding_model -ne $EmbeddingModel -or $body.reranker_model -ne $RerankerModel) { return $false }
        if ($RequireReady -and ($body.engine_ready -ne $true -or $body.qdrant_ready -ne $true -or $body.models_ready -ne $true)) { return $false }
        return $true
    } catch { return $false }
}

function Get-CialBackendIdentity {
    param([int]$Port)
    try {
        $body = (Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 5).Content | ConvertFrom-Json
        if ($body.service -eq "cial-knowledge-os" -and $body.phase -eq "4.5") { return $body }
    } catch { }
    return $null
}

function Test-CialFrontend {
    param([int]$Port)
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port/login" -TimeoutSec 5
        if ($response.StatusCode -ne 200 -or $response.Content -notmatch "CIAL Knowledge OS" -or $response.Content -notmatch "<div id=.root.") { return $false }
        $assetMatch = [regex]::Match($response.Content, '<script[^>]+src="([^"]+)"')
        if (-not $assetMatch.Success) { return $false }
        $asset = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port$($assetMatch.Groups[1].Value)" -TimeoutSec 15
        return $asset.StatusCode -eq 200 -and $asset.Content -match [regex]::Escape("http://127.0.0.1:$BackendPort")
    } catch { return $false }
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

function Resolve-InstalledRuntimeParameters {
    $envMap = Get-EnvMap -Paths @((Join-Path $RepoRoot ".env"), (Join-Path $BackendRoot ".env"), (Join-Path $BackendRoot "backend\.env"))
    if (-not $QdrantUrlExplicit -and -not [string]::IsNullOrWhiteSpace($envMap["CIAL_QDRANT_URL"])) { $script:QdrantUrl = $envMap["CIAL_QDRANT_URL"] }
    if (-not $OllamaModelExplicit -and -not [string]::IsNullOrWhiteSpace($envMap["CIAL_OLLAMA_MODEL_NAME"])) { $script:OllamaModel = $envMap["CIAL_OLLAMA_MODEL_NAME"] }
    if (-not $EmbeddingModelExplicit -and -not [string]::IsNullOrWhiteSpace($envMap["CIAL_EMBEDDING_MODEL_NAME"])) { $script:EmbeddingModel = $envMap["CIAL_EMBEDDING_MODEL_NAME"] }
    if (-not $RerankerModelExplicit -and -not [string]::IsNullOrWhiteSpace($envMap["CIAL_RERANKER_MODEL_NAME"])) { $script:RerankerModel = $envMap["CIAL_RERANKER_MODEL_NAME"] }
    if (Test-Path -LiteralPath $InstallStatePath -PathType Leaf) {
        try {
            $state = Get-Content -LiteralPath $InstallStatePath -Raw | ConvertFrom-Json
            $postgres = $state.stages.PSObject.Properties["postgresql"].Value
            if (-not $PostgresContainerExplicit -and -not [string]::IsNullOrWhiteSpace($postgres.container)) { $script:PostgresContainerName = $postgres.container }
            $startup = $state.stages.PSObject.Properties["startup"].Value
            if (-not $BackendPortExplicit -and -not [string]::IsNullOrWhiteSpace($startup.backend)) { $script:BackendPort = ([uri]$startup.backend).Port }
            if (-not $FrontendPortExplicit -and -not [string]::IsNullOrWhiteSpace($startup.frontend)) { $script:FrontendPort = ([uri]$startup.frontend).Port }
        } catch { }
    }
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
    if (-not (Test-Path -LiteralPath $InstallStatePath -PathType Leaf)) { Stop-Launch "Installer state is missing. Run Install-CIAL-Knowledge-OS.bat to validate/repair the installation." }
    $state = Get-Content -LiteralPath $InstallStatePath -Raw | ConvertFrom-Json
    if ($null -eq $state.stages) { Stop-Launch "Installer state uses an older or incomplete schema. Run the installer to revalidate it safely." }
    $backendStage = $state.stages.PSObject.Properties["backend-dependencies"].Value
    $frontendStage = $state.stages.PSObject.Properties["frontend-dependencies"].Value
    if ($null -eq $backendStage -or $null -eq $frontendStage) { Stop-Launch "Dependency verification state is incomplete. Run the installer to repair it." }
    $requirementsHash = (Get-FileHash -LiteralPath (Join-Path $BackendRoot "requirements.txt") -Algorithm SHA256).Hash
    $pyprojectHash = (Get-FileHash -LiteralPath (Join-Path $BackendRoot "pyproject.toml") -Algorithm SHA256).Hash
    $packageHash = (Get-FileHash -LiteralPath (Join-Path $FrontendRoot "package.json") -Algorithm SHA256).Hash
    $lockHash = (Get-FileHash -LiteralPath (Join-Path $FrontendRoot "pnpm-lock.yaml") -Algorithm SHA256).Hash
    if ($backendStage.requirements_hash -ne $requirementsHash -or $backendStage.pyproject_hash -ne $pyprojectHash -or $frontendStage.package_hash -ne $packageHash -or $frontendStage.lockfile_hash -ne $lockHash) {
        Stop-Launch "Dependency inputs changed after installation. The launcher will not install packages; run Install-CIAL-Knowledge-OS.bat for a fingerprint-based repair."
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
    $script:ExpectedRepositoryId = $repo[0].repository_id
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

function Get-DockerComposeTool {
    $docker = Get-CommandPath "docker.exe"
    & $docker compose version 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { return [pscustomobject]@{ File=$docker; Prefix=@("compose") } }
    foreach ($candidate in @(
        (Join-Path $env:ProgramFiles "Docker\Docker\resources\bin\docker-compose.exe"),
        (Join-Path $env:ProgramFiles "Docker\cli-plugins\docker-compose.exe")
    )) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return [pscustomobject]@{ File=$candidate; Prefix=@() } }
    }
    Stop-Launch "Docker Compose is unavailable. Run the installer to repair Docker Desktop."
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
        if (Test-PortOpen -HostName $hostName -Port $port) { Write-Host "PostgreSQL port is open; SQL verification follows."; return }
    }
    $containerName = $PostgresContainerName
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

function Verify-Postgres {
    $previousPythonPath = $env:PYTHONPATH
    $env:PYTHONPATH = "$BackendRoot;$BackendRoot\src"
    try { & $PythonExe -c "from sqlalchemy import create_engine,text; from backend.app.core.config import settings; e=create_engine(settings.database_url); c=e.connect(); assert c.execute(text('select 1')).scalar_one()==1; print('PostgreSQL SQL verification: OK'); c.close(); e.dispose()" }
    finally { $env:PYTHONPATH = $previousPythonPath }
    if ($LASTEXITCODE -ne 0) {
        $envMap=Get-EnvMap -Paths @((Join-Path $RepoRoot ".env"),(Join-Path $BackendRoot ".env"),(Join-Path $BackendRoot "backend\.env"))
        $dbPort=if($envMap["DATABASE_URL"] -match ":(\d+)/"){[int]$Matches[1]}else{5432}
        $owner=Get-PortProcessId -Port $dbPort
        Stop-Launch "PostgreSQL validation failed on port $dbPort (owner PID: $owner). No process or data was changed; rerun the installer for safe repair guidance."
    }
}

function Ensure-Qdrant {
    Write-Step "Checking Qdrant"
    $qdrantReady = Wait-Url -Url "$QdrantUrl/collections" -Seconds 5
    if ($qdrantReady) {
        Write-Host "Qdrant is already ready at $QdrantUrl."
    }
    if (-not $qdrantReady) {
        if (-not (Test-Path -LiteralPath $QdrantComposeFile -PathType Leaf)) { Stop-Launch "Missing Qdrant compose file: $QdrantComposeFile" }
        Ensure-Docker
        $existing = ((& docker.exe ps -a --format "{{.Names}}") -contains "cial-knowledge-os-v1-dev-qdrant")
        if ($existing) { & docker.exe start "cial-knowledge-os-v1-dev-qdrant" | Out-Null }
        else {
            $compose = Get-DockerComposeTool; & $compose.File @($compose.Prefix + @("-f", $QdrantComposeFile, "up", "-d"))
        }
        if ($LASTEXITCODE -ne 0) { Stop-Launch "Qdrant compose startup failed." }
        if (-not (Wait-Url -Url "$QdrantUrl/collections" -Seconds 90)) {
            $owner=Get-PortProcessId -Port ([uri]$QdrantUrl).Port
            Stop-Launch "Qdrant did not become ready at $QdrantUrl (port owner PID: $owner). Unrelated processes were not stopped."
        }
    }
    try {
        $identity = (Invoke-WebRequest -UseBasicParsing -Uri "$QdrantUrl/" -TimeoutSec 10).Content | ConvertFrom-Json
        $version = [version]$identity.version
        if ($identity.title -notmatch "qdrant" -or $version.Major -ne 1 -or $version.Minor -lt 15 -or $version.Minor -gt 18) { Stop-Launch "Unsupported or unrelated Qdrant service at $QdrantUrl." }
    } catch { Stop-Launch "Qdrant identity/version verification failed at $QdrantUrl." }
}

function Ensure-Ollama {
    Write-Step "Checking Ollama"
    $ollama = Get-CommandPath "ollama.exe"
    if ($null -eq $ollama) { $candidate=Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"; if(Test-Path -LiteralPath $candidate -PathType Leaf){$ollama=$candidate} }
    $ollamaReady=$false
    try {$tags=(Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 5).Content|ConvertFrom-Json;$ollamaReady=$null -ne $tags.models}catch{}
    if (-not $ollamaReady) {
        if(Test-PortOpen -HostName "127.0.0.1" -Port 11434){Stop-Launch "Port 11434 is occupied by a service that is not Ollama. It was not stopped."}
        if ($null -eq $ollama) { Stop-Launch "Ollama executable was not found." }
        Start-Process -FilePath $ollama -ArgumentList "serve" -WindowStyle Hidden
        if (-not (Wait-Url -Url "http://127.0.0.1:11434/api/tags" -Seconds 90)) { Stop-Launch "Ollama did not become ready." }
    }
    if ($null -eq $ollama) { $ollama = Get-CommandPath "ollama.exe" }
    $models = (& $ollama list) -join "`n"
    $modelNames=@($models -split "`r?`n"|Select-Object -Skip 1|ForEach-Object{($_ -split "\s+")[0]})
    if ($OllamaModel -notin $modelNames) { Stop-Launch "Required Ollama model $OllamaModel is missing. Run the installer to repair the installation." }
}

function Verify-CudaAndModels {
    Write-Step "Checking CUDA and local models"
    $env:TRANSFORMERS_OFFLINE = "1"; $env:HF_HUB_OFFLINE = "1"
    $code = "import torch; from sentence_transformers import SentenceTransformer,CrossEncoder; assert torch.cuda.is_available() and torch.version.cuda; SentenceTransformer('$EmbeddingModel',device='cuda',local_files_only=True); CrossEncoder('$RerankerModel',device='cuda',local_files_only=True); print(torch.__version__,torch.version.cuda,torch.cuda.get_device_name(0))"
    & $PythonExe -c $code
    if ($LASTEXITCODE -ne 0) { Stop-Launch "CUDA or required local model cache verification failed. Run the installer to repair it." }
}

function Ensure-AlembicCurrent {
    Write-Step "Checking database migrations"
    Push-Location $BackendRoot
    try {
        $heads = (& $PythonExe -m alembic heads) -join "`n"
        $current = (& $PythonExe -m alembic current) -join "`n"
        $head = ([regex]::Match($heads, "(?m)^([0-9A-Za-z_]+)\s+\(head\)")).Groups[1].Value
        if ([string]::IsNullOrWhiteSpace($head)) { Stop-Launch "Could not determine Alembic head." }
        if ($current -notmatch [regex]::Escape($head)) {
            & $PythonExe -m alembic upgrade head
            if ($LASTEXITCODE -ne 0) { Stop-Launch "Alembic migration upgrade failed." }
        }
    } finally { Pop-Location }
}

function Start-Backend {
    Write-Step "Checking backend"
    if (Test-CialBackend -Port $BackendPort -RequireReady) {
        Write-Host "Backend already responds on port $BackendPort."
        return
    }
    $portProcessId = Get-PortProcessId -Port $BackendPort
    if ($null -ne $portProcessId) {
        $knownCial = Get-CialBackendIdentity -Port $BackendPort
        if ($null -eq $knownCial) { Stop-Launch "Port $BackendPort is occupied by unrelated process $portProcessId. It was not stopped." }
        Write-Host "Stopping known CIAL backend process $portProcessId because its version, configuration, or readiness is stale."
        Stop-Process -Id $portProcessId -Force
        Start-Sleep -Seconds 2
    }
    $out = Join-Path $LogsRoot "backend-$Timestamp.out.log"
    $err = Join-Path $LogsRoot "backend-$Timestamp.err.log"
    $previousPythonPath = $env:PYTHONPATH
    $env:PYTHONPATH = "$BackendRoot;$BackendRoot\src"
    Start-Process -FilePath $PythonExe -ArgumentList @("-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "$BackendPort") -WorkingDirectory $BackendRoot -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err | Out-Null
    $env:PYTHONPATH = $previousPythonPath
    $reachable = $false
    $deadline = (Get-Date).AddSeconds(180)
    do { if (Test-CialBackend -Port $BackendPort) { $reachable=$true; break }; Start-Sleep -Seconds 2 } while ((Get-Date) -lt $deadline)
    if (-not $reachable) {
        Stop-Launch "Backend did not become reachable. See $out and $err."
    }
    $ready = $false; $deadline = (Get-Date).AddSeconds(300)
    do { if (Test-CialBackend -Port $BackendPort -RequireReady) { $ready=$true; break }; Start-Sleep -Seconds 3 } while ((Get-Date) -lt $deadline)
    if (-not $ready) {
        Stop-Launch "Backend reached HTTP health but did not become ready. Check backend startup logs."
    }
}

function Start-Frontend {
    Write-Step "Checking frontend"
    if (Test-CialFrontend -Port $FrontendPort) {
        Write-Host "Frontend already responds on port $FrontendPort."
        return
    }
    $portProcessId = Get-PortProcessId -Port $FrontendPort
    if ($null -ne $portProcessId) {
        try {
            $page = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$FrontendPort/login" -TimeoutSec 5
            $knownCial = $page.StatusCode -eq 200 -and $page.Content -match "CIAL Knowledge OS"
        } catch { $knownCial = $false }
        if (-not $knownCial) { Stop-Launch "Port $FrontendPort is occupied by unrelated process $portProcessId. It was not stopped." }
        Stop-Launch "A known CIAL frontend is running with stale configuration on port $FrontendPort. Run the installer to rebuild it safely."
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
    $ready=$false; $deadline=(Get-Date).AddSeconds(90)
    do { if (Test-CialFrontend -Port $FrontendPort) { $ready=$true; break }; Start-Sleep -Seconds 2 } while ((Get-Date) -lt $deadline)
    if (-not $ready) {
        Stop-Launch "Frontend did not become reachable. See $out and $err."
    }
}

function Confirm-ApplicationStable {
    Write-Step "Confirming application readiness"
    Start-Sleep -Seconds 3
    if (-not (Test-CialBackend -Port $BackendPort -RequireReady)) {
        Stop-Launch "Backend readiness was not stable after startup."
    }
    if (-not (Test-CialFrontend -Port $FrontendPort)) {
        Stop-Launch "Frontend readiness was not stable after startup."
    }
}

try {
    Resolve-InstalledRuntimeParameters
    Assert-ApplicationFiles
    Assert-CorpusConfiguration
    Ensure-Postgres
    Verify-Postgres
    Ensure-Qdrant
    Ensure-Ollama
    Verify-CudaAndModels
    Ensure-AlembicCurrent
    Start-Backend
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
