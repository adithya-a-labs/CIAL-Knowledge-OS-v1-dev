param(
    [string]$CorpusRepositoryPath = "",
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [int]$PostgresPort = 5432,
    [string]$PostgresContainerName = "cial-knowledge-os-v1-dev-postgres",
    [string]$PostgresVolumeName = "cial_postgres_data",
    [string]$QdrantComposeFile = "",
    [string]$QdrantUrl = "http://localhost:6335",
    [string]$OllamaModel = "gemma3:12b",
    [string]$EmbeddingModel = "BAAI/bge-m3",
    [string]$RerankerModel = "cross-encoder/ms-marco-MiniLM-L-6-v2",
    [switch]$SkipPrerequisiteInstall,
    [switch]$SkipModelSmoke,
    [switch]$VerifyCleanFrontendInstall,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$RepoRoot = $PSScriptRoot
$BackendRoot = Join-Path $RepoRoot "services\knowledge-engine"
$FrontendRoot = Join-Path $RepoRoot "frontend"
$VenvRoot = Join-Path $RepoRoot ".venv"
$PythonExe = Join-Path $VenvRoot "Scripts\python.exe"
$LogsRoot = Join-Path $RepoRoot "outputs\installer\logs"
$StateRoot = Join-Path $RepoRoot "outputs\installer\runtime"
$AppConfigPath = Join-Path $RepoRoot "data\config\application.json"
$BackendEnvPath = Join-Path $BackendRoot "backend\.env"
$FrontendEnvPath = Join-Path $FrontendRoot ".env"
if ([string]::IsNullOrWhiteSpace($QdrantComposeFile)) {
    $QdrantComposeFile = Join-Path $BackendRoot "docker-compose.qdrant.yml"
}

New-Item -ItemType Directory -Force -Path $LogsRoot, $StateRoot | Out-Null
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$LogPath = Join-Path $LogsRoot "install-$Timestamp.log"
Start-Transcript -Path $LogPath -Append | Out-Null

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "== $Message ==" -ForegroundColor Cyan
}

function Stop-Install {
    param([string]$Message)
    Write-Host ""
    Write-Host $Message -ForegroundColor Red
    throw $Message
}

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-CommandPath {
    param([string]$Name)
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -eq $command) { return $null }
    return $command.Source
}

function Invoke-Logged {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$WorkingDirectory = $RepoRoot,
        [string]$FailureMessage = ""
    )
    Write-Host "Running: $FilePath $($Arguments -join ' ')"
    $process = Start-Process -FilePath $FilePath -ArgumentList $Arguments -WorkingDirectory $WorkingDirectory -NoNewWindow -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        if ([string]::IsNullOrWhiteSpace($FailureMessage)) {
            $FailureMessage = "Command failed with exit code $($process.ExitCode): $FilePath"
        }
        Stop-Install $FailureMessage
    }
}

function Invoke-Capture {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$WorkingDirectory = $RepoRoot
    )
    $previous = (Get-Location).ProviderPath
    try {
        Set-Location -LiteralPath $WorkingDirectory
        $output = & $FilePath @Arguments 2>&1
        $exitCode = $LASTEXITCODE
        return [pscustomobject]@{
            ExitCode = $exitCode
            Output = (($output | ForEach-Object { "$_" }) -join "`n").Trim()
        }
    }
    catch {
        return [pscustomobject]@{
            ExitCode = 1
            Output = $_.Exception.Message
        }
    }
    finally {
        Set-Location -LiteralPath $previous
    }
}

function Test-ExecutableVersion {
    param(
        [string]$Label,
        [string]$FilePath,
        [string[]]$Arguments = @("--version")
    )
    if ([string]::IsNullOrWhiteSpace($FilePath) -or -not (Test-Path -LiteralPath $FilePath -PathType Leaf)) {
        return [pscustomobject]@{
            Ok = $false
            Version = ""
            Error = "$Label executable was not found at $FilePath"
        }
    }
    $result = Invoke-Capture -FilePath $FilePath -Arguments $Arguments
    if ($result.ExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($result.Output)) {
        return [pscustomobject]@{
            Ok = $false
            Version = ""
            Error = "$Label validation failed at $FilePath. Output: $($result.Output)"
        }
    }
    return [pscustomobject]@{
        Ok = $true
        Version = ($result.Output -split "`r?`n" | Select-Object -First 1)
        Error = ""
    }
}

function Refresh-ProcessPath {
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $paths = @($machinePath, $userPath, $env:Path) -join ";"
    $deduped = New-Object System.Collections.Generic.List[string]
    foreach ($entry in ($paths -split ";")) {
        if ([string]::IsNullOrWhiteSpace($entry)) { continue }
        $expanded = [Environment]::ExpandEnvironmentVariables($entry.Trim())
        if ([string]::IsNullOrWhiteSpace($expanded)) { continue }
        if (-not ($deduped | Where-Object { $_ -ieq $expanded })) {
            $deduped.Add($expanded) | Out-Null
        }
    }
    $env:Path = ($deduped -join ";")
}

function Remove-PathEntryForCurrentProcess {
    param([string]$Directory)
    if ([string]::IsNullOrWhiteSpace($Directory)) { return }
    $env:Path = (($env:Path -split ";") | Where-Object {
        -not [string]::IsNullOrWhiteSpace($_) -and $_.TrimEnd("\") -ine $Directory.TrimEnd("\")
    }) -join ";"
}

function Get-RequiredPnpmVersion {
    $packageJsonPath = Join-Path $FrontendRoot "package.json"
    if (Test-Path -LiteralPath $packageJsonPath -PathType Leaf) {
        $packageJson = Get-Content -LiteralPath $packageJsonPath -Raw | ConvertFrom-Json
        if ($packageJson.packageManager -match "^pnpm@(.+)$") {
            return $matches[1]
        }
    }

    $lockfilePath = Join-Path $FrontendRoot "pnpm-lock.yaml"
    if (Test-Path -LiteralPath $lockfilePath -PathType Leaf) {
        $lockVersionLine = Select-String -Path $lockfilePath -Pattern "^lockfileVersion:\s*'?([^']+)'?" | Select-Object -First 1
        if ($null -ne $lockVersionLine -and $lockVersionLine.Matches[0].Groups[1].Value.StartsWith("9.")) {
            return "10.33.4"
        }
    }

    Stop-Install "Unable to determine required pnpm version. Add a packageManager field to frontend\package.json."
}

function Get-OfficialNodePath {
    return (Join-Path $env:ProgramFiles "nodejs\node.exe")
}

function Test-NvmManagedNodeDirectory {
    param([string]$NodeDir)
    if ([string]::IsNullOrWhiteSpace($NodeDir)) { return $false }
    $normalized = $NodeDir.ToLowerInvariant()
    if ($normalized -like "*\nvm4w\*" -or $normalized -like "*\appdata\local\nvm\*") {
        return $true
    }
    $nodeModules = Join-Path $NodeDir "node_modules"
    if (Test-Path -LiteralPath $nodeModules) {
        $item = Get-Item -LiteralPath $nodeModules -Force
        $targetText = (@($item.Target) -join ";").ToLowerInvariant()
        if ($targetText -like "*\appdata\local\nvm\*") {
            return $true
        }
    }
    return $false
}

function Install-OfficialNodeLtsSideBySide {
    param([string]$BrokenNodeDir)
    $officialNode = Get-OfficialNodePath
    if (Test-Path -LiteralPath $officialNode -PathType Leaf) {
        Write-Host "Official Node.js LTS is already present at $officialNode."
        return $officialNode
    }
    if ($SkipPrerequisiteInstall) {
        Stop-Install "Node was detected under an NVM-managed path with broken npm/Corepack: $BrokenNodeDir. Install official Node.js LTS at C:\Program Files\nodejs or rerun without -SkipPrerequisiteInstall."
    }

    Write-Host "Node was detected under an NVM-managed path with broken npm/Corepack: $BrokenNodeDir"
    Write-Host "The installer will not attempt to repair NVM."
    $answer = Read-Host "Install official Node.js LTS side-by-side through winget and retry using C:\Program Files\nodejs? [Y/N]"
    if ($answer -notmatch "^(Y|y|YES|yes)$") {
        Stop-Install "Official Node.js LTS installation was declined. Repair NVM manually or install Node.js LTS at C:\Program Files\nodejs, then rerun."
    }

    $winget = Get-CommandPath "winget.exe"
    if ($null -eq $winget) {
        Stop-Install "winget is required to install official Node.js LTS. Install App Installer from Microsoft Store or install Node.js LTS manually."
    }
    Invoke-Logged -FilePath $winget -Arguments @("install", "--id", "OpenJS.NodeJS.LTS", "--exact", "--silent", "--accept-package-agreements", "--accept-source-agreements") -FailureMessage "winget could not install official Node.js LTS."
    Refresh-ProcessPath
    if (-not (Test-Path -LiteralPath $officialNode -PathType Leaf)) {
        Stop-Install "winget completed but official Node.js LTS was not found at $officialNode. Restart the elevated terminal or install Node.js LTS manually."
    }
    return $officialNode
}

function Get-NodeCandidates {
    Refresh-ProcessPath
    $paths = New-Object System.Collections.Generic.List[string]
    $programFilesNode = Get-OfficialNodePath
    if (Test-Path -LiteralPath $programFilesNode -PathType Leaf) {
        $paths.Add($programFilesNode) | Out-Null
    }
    foreach ($command in @(Get-Command "node.exe" -All -ErrorAction SilentlyContinue)) {
        if ($null -ne $command.Source -and -not ($paths | Where-Object { $_ -ieq $command.Source })) {
            $paths.Add($command.Source) | Out-Null
        }
    }
    return @($paths)
}

function Resolve-NodeFrontendToolchain {
    param([switch]$OfficialNodeFallbackAlreadyOffered)
    Write-Step "Resolving Node.js frontend toolchain"
    $requiredPnpmVersion = Get-RequiredPnpmVersion
    Write-Host "Required pnpm version: $requiredPnpmVersion"

    $brokenDirectories = New-Object System.Collections.Generic.List[string]
    foreach ($node in Get-NodeCandidates) {
        $nodeDir = Split-Path -Parent $node
        $npm = Join-Path $nodeDir "npm.cmd"
        $corepack = Join-Path $nodeDir "corepack.cmd"

        $nodeCheck = Test-ExecutableVersion -Label "node" -FilePath $node
        if (-not $nodeCheck.Ok) {
            Write-Host "Ignoring Node candidate: $($nodeCheck.Error)"
            $brokenDirectories.Add($nodeDir) | Out-Null
            continue
        }

        $npmCheck = Test-ExecutableVersion -Label "npm" -FilePath $npm
        $corepackCheck = Test-ExecutableVersion -Label "corepack" -FilePath $corepack
        if (-not $npmCheck.Ok) { Write-Host "npm shim is not usable: $($npmCheck.Error)" }
        if (-not $corepackCheck.Ok) { Write-Host "corepack shim is not usable: $($corepackCheck.Error)" }

        if (-not $npmCheck.Ok -and -not $corepackCheck.Ok) {
            if (-not $OfficialNodeFallbackAlreadyOffered -and (Test-NvmManagedNodeDirectory -NodeDir $nodeDir)) {
                $brokenDirectories.Add($nodeDir) | Out-Null
                Install-OfficialNodeLtsSideBySide -BrokenNodeDir $nodeDir | Out-Null
                Remove-PathEntryForCurrentProcess -Directory $nodeDir
                return Resolve-NodeFrontendToolchain -OfficialNodeFallbackAlreadyOffered
            }
            Write-Host "Ignoring Node directory because both npm and Corepack are unusable: $nodeDir"
            $brokenDirectories.Add($nodeDir) | Out-Null
            continue
        }

        foreach ($broken in $brokenDirectories) {
            Remove-PathEntryForCurrentProcess -Directory $broken
        }
        $env:Path = "$nodeDir;$env:Path"

        $pnpm = Resolve-PnpmFromNode -NodeDir $nodeDir -Corepack $corepack -CorepackOk $corepackCheck.Ok -Npm $npm -NpmOk $npmCheck.Ok -RequiredVersion $requiredPnpmVersion
        $pnpmCheck = Test-ExecutableVersion -Label "pnpm" -FilePath $pnpm
        if (-not $pnpmCheck.Ok) {
            Stop-Install "Resolved pnpm executable failed validation: $($pnpmCheck.Error)"
        }

        Write-Host "node: $node ($($nodeCheck.Version))"
        Write-Host "npm: $npm ($(if ($npmCheck.Ok) { $npmCheck.Version } else { "unusable" }))"
        Write-Host "corepack: $corepack ($(if ($corepackCheck.Ok) { $corepackCheck.Version } else { "unusable" }))"
        Write-Host "pnpm: $pnpm ($($pnpmCheck.Version))"

        return [pscustomobject]@{
            Node = $node
            Npm = $npm
            Corepack = $corepack
            Pnpm = $pnpm
            NodeDir = $nodeDir
            PnpmVersion = $pnpmCheck.Version
        }
    }

    Stop-Install "No usable Node.js toolchain was found. Install or repair Node.js LTS, then rerun the installer from a new elevated terminal."
}

function Resolve-PnpmFromNode {
    param(
        [string]$NodeDir,
        [string]$Corepack,
        [bool]$CorepackOk,
        [string]$Npm,
        [bool]$NpmOk,
        [string]$RequiredVersion
    )

    $pnpmCmd = Join-Path $NodeDir "pnpm.cmd"
    if ($CorepackOk) {
        Write-Host "Activating pnpm@$RequiredVersion through Node.js Corepack."
        $enable = Invoke-Capture -FilePath $Corepack -Arguments @("enable")
        $prepare = Invoke-Capture -FilePath $Corepack -Arguments @("prepare", "pnpm@$RequiredVersion", "--activate")
        if ($enable.ExitCode -eq 0 -and $prepare.ExitCode -eq 0 -and (Test-Path -LiteralPath $pnpmCmd -PathType Leaf)) {
            return $pnpmCmd
        }
        Write-Host "Corepack activation failed; output: $($enable.Output) $($prepare.Output)"
    }

    if ($NpmOk) {
        Write-Host "Installing pnpm@$RequiredVersion through the verified Node.js npm."
        $install = Invoke-Capture -FilePath $Npm -Arguments @("install", "--global", "pnpm@$RequiredVersion")
        if ($install.ExitCode -eq 0 -and (Test-Path -LiteralPath $pnpmCmd -PathType Leaf)) {
            return $pnpmCmd
        }
        Stop-Install "npm fallback could not install pnpm@$RequiredVersion. Output: $($install.Output)"
    }

    Stop-Install "Corepack could not activate pnpm and npm is not usable for fallback installation."
}

function Remove-DirectorySafely {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return }
    $resolvedTarget = (Resolve-Path -LiteralPath $Path).Path
    $resolvedRepo = (Resolve-Path -LiteralPath $RepoRoot).Path
    if (-not $resolvedTarget.StartsWith($resolvedRepo, [StringComparison]::OrdinalIgnoreCase)) {
        Stop-Install "Refusing to remove a directory outside the repository: $resolvedTarget"
    }
    Remove-Item -LiteralPath $resolvedTarget -Recurse -Force
}

function Ensure-WingetPackage {
    param(
        [string]$Id,
        [string]$DisplayName
    )
    if ($SkipPrerequisiteInstall) {
        Write-Host "Skipping installation check for $DisplayName because -SkipPrerequisiteInstall was supplied."
        return
    }
    $winget = Get-CommandPath "winget.exe"
    if ($null -eq $winget) {
        Stop-Install "winget is required to install missing prerequisites automatically. Install App Installer from Microsoft Store or rerun with prerequisites installed."
    }
    Write-Host "Verifying/installing $DisplayName ($Id) via winget."
    & $winget list --id $Id --exact --accept-source-agreements | Out-Null
    if ($LASTEXITCODE -eq 0) {
        return
    }
    & $winget install --id $Id --exact --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        Stop-Install "winget could not install $DisplayName ($Id). Install it manually and rerun."
    }
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

function Get-EnvMap {
    param([string[]]$Paths)
    $map = @{}
    foreach ($path in $Paths) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { continue }
        foreach ($line in Get-Content -LiteralPath $path) {
            $trimmed = $line.Trim()
            if ([string]::IsNullOrWhiteSpace($trimmed) -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) { continue }
            $parts = $trimmed.Split("=", 2)
            $key = $parts[0].Trim()
            $value = $parts[1].Trim()
            if ($value.Length -ge 2 -and (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'")))) {
                $value = $value.Substring(1, $value.Length - 2)
            }
            $map[$key] = $value
        }
    }
    return $map
}

function Set-EnvFileValue {
    param(
        [string]$Path,
        [hashtable]$Values
    )
    $lines = @()
    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        $lines = @(Get-Content -LiteralPath $Path)
    }
    foreach ($key in $Values.Keys) {
        $found = $false
        for ($i = 0; $i -lt $lines.Count; $i++) {
            if ($lines[$i] -match "^\s*$([regex]::Escape($key))\s*=") {
                $lines[$i] = "$key=$($Values[$key])"
                $found = $true
                break
            }
        }
        if (-not $found) {
            $lines += "$key=$($Values[$key])"
        }
    }
    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $lines | Set-Content -LiteralPath $Path -Encoding UTF8
}

function Get-DatabaseUrl {
    $map = Get-EnvMap -Paths @((Join-Path $RepoRoot ".env"), (Join-Path $BackendRoot ".env"), $BackendEnvPath)
    if ($map.ContainsKey("DATABASE_URL") -and -not [string]::IsNullOrWhiteSpace($map["DATABASE_URL"])) {
        return $map["DATABASE_URL"]
    }
    return $null
}

function New-Password {
    $bytes = New-Object byte[] 24
    [Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    return [Convert]::ToBase64String($bytes).TrimEnd("=") -replace "[+/]", "A"
}

function Ensure-BackendEnv {
    Write-Step "Preparing backend environment file"
    $databaseUrl = Get-DatabaseUrl
    if ([string]::IsNullOrWhiteSpace($databaseUrl)) {
        $password = New-Password
        $databaseUrl = "postgresql+psycopg://postgres:$password@localhost:$PostgresPort/cial_knowledge_os_dev"
        Set-Content -LiteralPath (Join-Path $StateRoot "postgres-password.txt") -Value $password -Encoding UTF8
        Write-Host "Generated PostgreSQL password and stored it under outputs\installer\runtime."
    }
    Set-EnvFileValue -Path $BackendEnvPath -Values @{
        "CIAL_AUTO_INDEX_ON_STARTUP" = "false"
        "CIAL_FORCE_REBUILD_ON_STARTUP" = "false"
        "CIAL_STARTUP_INDEX_TIMEOUT_SECONDS" = "0"
        "CIAL_APP_DATA_DIR" = "data"
        "CIAL_OUTPUTS_DIR" = "outputs"
        "CIAL_MODELS_DIR" = "models"
        "DATABASE_URL" = $databaseUrl
        "CIAL_CORPUS_SYNC_ON_STARTUP" = "false"
        "CIAL_CORPUS_WATCH" = "true"
        "CIAL_CORPUS_WATCH_DEBOUNCE_MS" = "750"
        "CIAL_CORPUS_FILE_STABILITY_INTERVAL_MS" = "500"
        "CIAL_CORPUS_FILE_STABILITY_CHECKS" = "3"
        "CIAL_CORPUS_RECONCILE_INTERVAL_SECONDS" = "300"
        "CIAL_QDRANT_MODE" = "server"
        "CIAL_QDRANT_URL" = $QdrantUrl
        "CIAL_QDRANT_BATCH_SIZE" = "32"
        "CIAL_QDRANT_UPSERT_WAIT" = "true"
        "QDRANT_TIMEOUT_SECONDS" = "30"
        "QDRANT_RETRY_ATTEMPTS" = "3"
        "QDRANT_RETRY_BACKOFF_SECONDS" = "2"
        "QDRANT_HEALTH_TIMEOUT_SECONDS" = "5"
        "QDRANT_QUERY_TIMEOUT_SECONDS" = "30"
        "QDRANT_UPSERT_TIMEOUT_SECONDS" = "60"
        "QDRANT_DELETE_TIMEOUT_SECONDS" = "60"
        "QDRANT_COLLECTION_TIMEOUT_SECONDS" = "120"
        "CIAL_INDEXER_ENABLED" = "true"
        "CIAL_INDEXER_WORKER_ID" = ""
        "CIAL_INDEXER_POLL_SECONDS" = "1"
        "CIAL_INDEXER_LEASE_SECONDS" = "120"
        "CIAL_INDEXER_HEARTBEAT_SECONDS" = "15"
        "CIAL_INDEXER_HEARTBEAT_STALE_SECONDS" = "45"
        "CIAL_INDEXER_MAX_ATTEMPTS" = "5"
        "CIAL_INDEXER_RETRY_BACKOFF_SECONDS" = "5"
        "CIAL_INDEXER_EXTRACTION_WORKERS" = "4"
        "CIAL_INDEXER_PREPARED_QUEUE_SIZE" = "8"
        "CIAL_INDEXER_EMBED_QUEUE_SIZE" = "4096"
        "CIAL_INDEXER_WRITE_QUEUE_SIZE" = "16"
        "CIAL_INDEXER_EMBED_BATCH_SIZE" = "64"
        "CIAL_INDEXER_EMBED_MAX_BATCH_TOKENS" = "32768"
        "CIAL_INDEXER_EMBED_MAX_WAIT_MS" = "75"
        "CIAL_INDEXER_QDRANT_BATCH_SIZE" = "128"
        "CIAL_INDEXER_DEVICE" = "auto"
        "CIAL_INDEXER_PRECISION" = "auto"
        "CIAL_INDEXER_GPU_POLICY" = "balanced"
        "CIAL_BM25_REFRESH_DEBOUNCE_SECONDS" = "2"
        "CIAL_OLLAMA_MODEL_NAME" = $OllamaModel
        "CIAL_EMBEDDING_MODEL_NAME" = $EmbeddingModel
        "CIAL_RERANKER_MODEL_NAME" = $RerankerModel
        "CIAL_RERANKER_DEVICE" = "auto"
        "CIAL_RERANKER_BATCH_SIZE" = "16"
        "CIAL_LOCAL_FILES_ONLY" = "true"
        "TRANSFORMERS_OFFLINE" = "1"
        "HF_HUB_OFFLINE" = "1"
    }
    Write-Host "Backend .env prepared. DATABASE_URL value was not printed."
}

function Ensure-FrontendEnv {
    Write-Step "Preparing frontend environment file"
    Set-EnvFileValue -Path $FrontendEnvPath -Values @{
        "VITE_API_BASE_URL" = "http://127.0.0.1:$BackendPort"
        "VITE_ENABLE_AUTH" = "true"
        "VITE_ENABLE_REAL_AI" = "true"
    }
}

function Ensure-DockerDesktop {
    Write-Step "Starting Docker Desktop"
    $docker = Get-CommandPath "docker.exe"
    if ($null -eq $docker) {
        Stop-Install "Docker CLI was not found after prerequisite installation. Restart the terminal or install Docker Desktop manually."
    }
    & $docker info | Out-Null
    if ($LASTEXITCODE -eq 0) {
        return
    }
    $dockerDesktop = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
    if (Test-Path -LiteralPath $dockerDesktop) {
        Start-Process -FilePath $dockerDesktop -WindowStyle Hidden
    }
    $deadline = (Get-Date).AddMinutes(5)
    do {
        Start-Sleep -Seconds 5
        & $docker info | Out-Null
        if ($LASTEXITCODE -eq 0) {
            return
        }
    } while ((Get-Date) -lt $deadline)
    Stop-Install "Docker Desktop did not become ready. Start Docker Desktop, complete WSL2/restart prompts if shown, then rerun the installer."
}

function Ensure-Postgres {
    Write-Step "Starting PostgreSQL"
    $docker = Get-CommandPath "docker.exe"
    $databaseUrl = Get-DatabaseUrl
    if ($databaseUrl -match "@([^:/]+):(\d+)/") {
        $hostName = $Matches[1]
        $port = [int]$Matches[2]
        if (($hostName -in @("localhost", "127.0.0.1")) -and (Test-PortOpen -HostName "127.0.0.1" -Port $port)) {
            Write-Host "PostgreSQL is already reachable at ${hostName}:$port."
            return
        }
    }
    $passwordFile = Join-Path $StateRoot "postgres-password.txt"
    if (-not (Test-Path -LiteralPath $passwordFile -PathType Leaf)) {
        Stop-Install "PostgreSQL is not reachable and no installer-managed password file exists. Configure DATABASE_URL in backend\.env or rerun after removing the incomplete installer state."
    }
    $password = (Get-Content -LiteralPath $passwordFile -Raw).Trim()
    $containerExists = ((& $docker ps -a --format "{{.Names}}") -contains $PostgresContainerName)
    if (-not $containerExists) {
        & $docker run -d --name $PostgresContainerName `
            -e POSTGRES_USER=postgres `
            -e POSTGRES_PASSWORD=$password `
            -e POSTGRES_DB=cial_knowledge_os_dev `
            -p "$PostgresPort`:5432" `
            -v "$PostgresVolumeName`:/var/lib/postgresql/data" `
            postgres:18 | Out-Null
    }
    else {
        & $docker start $PostgresContainerName | Out-Null
    }
    $deadline = (Get-Date).AddMinutes(2)
    do {
        Start-Sleep -Seconds 3
        if (Test-PortOpen -HostName "127.0.0.1" -Port $PostgresPort) { return }
    } while ((Get-Date) -lt $deadline)
    Stop-Install "PostgreSQL did not become reachable on port $PostgresPort."
}

function Ensure-Qdrant {
    Write-Step "Starting Qdrant"
    if (-not (Test-Path -LiteralPath $QdrantComposeFile -PathType Leaf)) {
        Stop-Install "Qdrant compose file was not found: $QdrantComposeFile"
    }
    Invoke-Logged -FilePath "docker.exe" -Arguments @("compose", "-f", $QdrantComposeFile, "up", "-d") -WorkingDirectory $BackendRoot -FailureMessage "Qdrant compose startup failed."
    if (-not (Wait-Url -Url "$QdrantUrl/collections" -Seconds 90)) {
        Stop-Install "Qdrant did not become ready at $QdrantUrl."
    }
}

function Ensure-Ollama {
    Write-Step "Starting Ollama and verifying model"
    $ollama = Get-CommandPath "ollama.exe"
    if ($null -eq $ollama) {
        Stop-Install "Ollama was not found after prerequisite installation. Restart the terminal or install Ollama manually."
    }
    try {
        Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 5 | Out-Null
    }
    catch {
        Start-Process -FilePath $ollama -ArgumentList "serve" -WindowStyle Hidden
    }
    if (-not (Wait-Url -Url "http://127.0.0.1:11434/api/tags" -Seconds 90)) {
        Stop-Install "Ollama did not become ready at http://127.0.0.1:11434."
    }
    $models = (& $ollama list) -join "`n"
    if ($models -notmatch [regex]::Escape($OllamaModel)) {
        Stop-Install "Required Ollama model '$OllamaModel' is not installed. Run: ollama pull $OllamaModel"
    }
}

function Ensure-PythonEnvironment {
    Write-Step "Creating Python 3.11 virtual environment"
    $py = Get-CommandPath "py.exe"
    if ($null -ne $py) {
        & $py -3.11 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,11) else 1)"
        if ($LASTEXITCODE -ne 0) { Stop-Install "Python 3.11 launcher exists but Python 3.11 is unavailable." }
        if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
            Invoke-Logged -FilePath $py -Arguments @("-3.11", "-m", "venv", $VenvRoot) -FailureMessage "Could not create Python 3.11 virtual environment."
        }
    }
    else {
        $python = Get-CommandPath "python.exe"
        if ($null -eq $python) { Stop-Install "Python was not found after prerequisite installation." }
        & $python -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,11) else 1)"
        if ($LASTEXITCODE -ne 0) { Stop-Install "python.exe is not Python 3.11. Install Python 3.11 and rerun." }
        if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
            Invoke-Logged -FilePath $python -Arguments @("-m", "venv", $VenvRoot) -FailureMessage "Could not create Python 3.11 virtual environment."
        }
    }
    Invoke-Logged -FilePath $PythonExe -Arguments @("-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel") -FailureMessage "pip bootstrap failed."
    Invoke-Logged -FilePath $PythonExe -Arguments @("-m", "pip", "install", "--upgrade", "--index-url", "https://download.pytorch.org/whl/cu132", "torch==2.13.0") -FailureMessage "CUDA-enabled PyTorch installation failed. CPU-only PyTorch is not allowed."
    Invoke-Logged -FilePath $PythonExe -Arguments @("-m", "pip", "install", "-r", (Join-Path $BackendRoot "requirements.txt")) -FailureMessage "Backend dependency installation failed."
    Invoke-Logged -FilePath $PythonExe -Arguments @("-m", "pip", "install", "-e", $BackendRoot) -FailureMessage "Editable backend package installation failed."
    & $PythonExe -c "import importlib.metadata, watchdog; print('watchdog=' + importlib.metadata.version('watchdog'))"
    if ($LASTEXITCODE -ne 0) {
        Stop-Install "The canonical requirements install did not provide watchdog."
    }
}

function Verify-Cuda {
    Write-Step "Verifying CUDA-enabled PyTorch"
    $env:TRANSFORMERS_OFFLINE = "1"
    $env:HF_HUB_OFFLINE = "1"
    $script = @"
import torch
print("torch.__version__=" + str(torch.__version__))
print("torch.version.cuda=" + str(torch.version.cuda))
print("torch.cuda.is_available()=" + str(torch.cuda.is_available()))
print("torch.cuda.device_count()=" + str(torch.cuda.device_count()))
print("gpu=" + (torch.cuda.get_device_name(0) if torch.cuda.is_available() else "NONE"))
raise SystemExit(0 if torch.cuda.is_available() and torch.version.cuda else 42)
"@
    $script | & $PythonExe -
    if ($LASTEXITCODE -ne 0) {
        Stop-Install "CUDA is unavailable to PyTorch. Installation stopped; CPU mode is not supported."
    }
}

function Verify-ModelCaches {
    if ($SkipModelSmoke) {
        Write-Host "Skipping embedding/reranker cache smoke tests because -SkipModelSmoke was supplied."
        return
    }
    Write-Step "Verifying embedding and reranker CUDA smoke tests"
    $env:TRANSFORMERS_OFFLINE = "1"
    $env:HF_HUB_OFFLINE = "1"
    $script = @"
from sentence_transformers import SentenceTransformer, CrossEncoder
embedding_model = SentenceTransformer("$EmbeddingModel", device="cuda")
embedding = embedding_model.encode(["CIAL CUDA embedding smoke test"], convert_to_tensor=True)
print("embedding_device=" + str(embedding.device))
reranker = CrossEncoder("$RerankerModel", device="cuda")
score = reranker.predict([("query", "document")])
print("reranker_score=" + str(score[0]))
"@
    $script | & $PythonExe -
    if ($LASTEXITCODE -ne 0) {
        Stop-Install "Embedding or reranker model cache verification failed. Ensure models are available locally, then rerun."
    }
}

function Verify-OcrAndOffice {
    Write-Step "Verifying Tesseract and LibreOffice"
    $tesseract = Get-CommandPath "tesseract.exe"
    if ($null -eq $tesseract) {
        $candidate = Join-Path $env:ProgramFiles "Tesseract-OCR\tesseract.exe"
        if (Test-Path -LiteralPath $candidate) { $tesseract = $candidate }
    }
    if ($null -eq $tesseract) { Stop-Install "Tesseract was not found." }
    & $tesseract --version | Select-Object -First 1

    $soffice = Get-CommandPath "soffice.exe"
    if ($null -eq $soffice) {
        $candidate = Join-Path $env:ProgramFiles "LibreOffice\program\soffice.exe"
        if (Test-Path -LiteralPath $candidate) { $soffice = $candidate }
    }
    if ($null -eq $soffice) { Stop-Install "LibreOffice soffice.exe was not found." }
    & $soffice --version
}

function Ensure-NodeFrontend {
    Write-Step "Installing and building frontend"
    $toolchain = Resolve-NodeFrontendToolchain
    Invoke-Logged -FilePath $toolchain.Pnpm -Arguments @("install", "--frozen-lockfile") -WorkingDirectory $FrontendRoot -FailureMessage "Frontend pnpm install failed."

    if ($VerifyCleanFrontendInstall) {
        Invoke-CleanFrontendInstallVerification -Pnpm $toolchain.Pnpm
    }

    $vite = Join-Path $FrontendRoot "node_modules\.bin\vite.cmd"
    $tsc = Join-Path $FrontendRoot "node_modules\.bin\tsc.cmd"
    if (-not (Test-Path -LiteralPath $vite -PathType Leaf)) {
        Stop-Install "Local Vite executable was not found after dependency installation: $vite"
    }
    if (-not (Test-Path -LiteralPath $tsc -PathType Leaf)) {
        Stop-Install "Local TypeScript executable was not found after dependency installation: $tsc"
    }
    $env:PORT = "$FrontendPort"
    $env:VITE_API_BASE_URL = "http://127.0.0.1:$BackendPort"
    Invoke-Logged -FilePath $vite -Arguments @("build") -WorkingDirectory $FrontendRoot -FailureMessage "Frontend production build failed."
    Invoke-Logged -FilePath $tsc -Arguments @("-p", "tsconfig.json", "--noEmit") -WorkingDirectory $FrontendRoot -FailureMessage "Frontend typecheck failed."
}

function Invoke-CleanFrontendInstallVerification {
    param([string]$Pnpm)

    Write-Step "Verifying clean frontend dependency installation"
    $nodeModules = Join-Path $FrontendRoot "node_modules"
    $backup = Join-Path $FrontendRoot ("node_modules.installer-backup-{0}" -f (Get-Date -Format "yyyyMMddHHmmss"))
    $movedExisting = $false

    if (Test-Path -LiteralPath $backup) {
        Stop-Install "Clean install verification backup path already exists: $backup"
    }

    try {
        if (Test-Path -LiteralPath $nodeModules -PathType Container) {
            Write-Host "Temporarily moving existing node_modules to $backup"
            Move-Item -LiteralPath $nodeModules -Destination $backup
            $movedExisting = $true
        }

        Invoke-Logged -FilePath $Pnpm -Arguments @("install", "--frozen-lockfile") -WorkingDirectory $FrontendRoot -FailureMessage "Clean frontend pnpm install failed."

        $vite = Join-Path $FrontendRoot "node_modules\.bin\vite.cmd"
        $tsc = Join-Path $FrontendRoot "node_modules\.bin\tsc.cmd"
        if (-not (Test-Path -LiteralPath $vite -PathType Leaf)) { Stop-Install "Clean install did not create local Vite executable: $vite" }
        if (-not (Test-Path -LiteralPath $tsc -PathType Leaf)) { Stop-Install "Clean install did not create local TypeScript executable: $tsc" }

        $env:PORT = "$FrontendPort"
        $env:VITE_API_BASE_URL = "http://127.0.0.1:$BackendPort"
        Invoke-Logged -FilePath $vite -Arguments @("build") -WorkingDirectory $FrontendRoot -FailureMessage "Clean frontend production build failed."
        Invoke-Logged -FilePath $tsc -Arguments @("-p", "tsconfig.json", "--noEmit") -WorkingDirectory $FrontendRoot -FailureMessage "Clean frontend typecheck failed."
        Write-Host "Clean frontend install verification succeeded."
    }
    finally {
        if ($movedExisting) {
            if (Test-Path -LiteralPath $nodeModules -PathType Container) {
                Write-Host "Removing clean verification node_modules before restoring the original directory."
                Remove-DirectorySafely -Path $nodeModules
            }
            if (Test-Path -LiteralPath $backup -PathType Container) {
                Write-Host "Restoring original node_modules from $backup"
                Move-Item -LiteralPath $backup -Destination $nodeModules
            }
        }
    }
}

function Ensure-CorpusConfiguration {
    Write-Step "Verifying enterprise repository configuration"
    $existingValid = $false
    if (Test-Path -LiteralPath $AppConfigPath -PathType Leaf) {
        try {
            $config = Get-Content -LiteralPath $AppConfigPath -Raw | ConvertFrom-Json
            $repo = @($config.repositories | Where-Object { $_.id -eq "enterprise" -and $_.enabled -ne $false } | Select-Object -First 1)
            if ($repo.Count -gt 0 -and (Test-Path -LiteralPath $repo[0].path -PathType Container)) {
                $existingValid = $true
                Write-Host "Existing enterprise repository config is valid and will be preserved: $($repo[0].path)"
            }
        }
        catch {
            Write-Host "Existing application config could not be parsed; first-run corpus selection is required."
        }
    }
    if ($existingValid) { return }
    $configScript = Join-Path $RepoRoot "scripts\configure_corpus_repository.ps1"
    if (-not (Test-Path -LiteralPath $configScript -PathType Leaf)) {
        Stop-Install "Missing corpus configuration helper: $configScript"
    }
    $arguments = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $configScript, "-ConfigPath", $AppConfigPath)
    if (-not [string]::IsNullOrWhiteSpace($CorpusRepositoryPath)) {
        $arguments += @("-RepositoryPath", $CorpusRepositoryPath)
    }
    Invoke-Logged -FilePath "powershell.exe" -Arguments $arguments -WorkingDirectory $RepoRoot -FailureMessage "Enterprise repository configuration failed or was cancelled."
}

function Run-Alembic {
    Write-Step "Running Alembic migrations"
    Push-Location $BackendRoot
    try {
        & $PythonExe -m alembic upgrade head
        if ($LASTEXITCODE -ne 0) { Stop-Install "alembic upgrade head failed." }
        $current = (& $PythonExe -m alembic current) -join "`n"
        $heads = (& $PythonExe -m alembic heads) -join "`n"
        Write-Host $current
        Write-Host $heads
        $headRevision = (($heads -split "\s+")[0]).Trim()
        if ([string]::IsNullOrWhiteSpace($headRevision) -or $current -notmatch [regex]::Escape($headRevision)) {
            Stop-Install "Alembic current revision is not at repository head."
        }
    }
    finally {
        Pop-Location
    }
}

function Start-Application {
    Write-Step "Starting application through daily launcher"
    $launcher = Join-Path $RepoRoot "Launch-CIAL-Knowledge-OS.ps1"
    Invoke-Logged -FilePath "powershell.exe" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $launcher, "-BackendPort", "$BackendPort", "-FrontendPort", "$FrontendPort", "-NoBrowser:$($NoBrowser.IsPresent)") -WorkingDirectory $RepoRoot -FailureMessage "Daily launcher failed during installer verification."
}

try {
    if (-not (Test-Administrator)) {
        Stop-Install "Run Install-CIAL-Knowledge-OS.bat as Administrator."
    }

    Write-Step "Deployment audit"
    Write-Host "Repository: $RepoRoot"
    Write-Host "Architecture: $env:PROCESSOR_ARCHITECTURE"
    $gpu = Get-CimInstance Win32_VideoController | Where-Object { $_.Name -match "NVIDIA" } | Select-Object -First 1
    if ($null -eq $gpu) { Stop-Install "No NVIDIA GPU was detected. CUDA-enabled installation cannot continue." }
    Write-Host "NVIDIA GPU: $($gpu.Name)"
    Write-Host "Driver version: $($gpu.DriverVersion)"

    Write-Step "Installing/verifying prerequisites"
    Ensure-WingetPackage -Id "Git.Git" -DisplayName "Git"
    Ensure-WingetPackage -Id "Python.Python.3.11" -DisplayName "Python 3.11"
    Ensure-WingetPackage -Id "OpenJS.NodeJS.LTS" -DisplayName "Node.js LTS"
    Ensure-WingetPackage -Id "Docker.DockerDesktop" -DisplayName "Docker Desktop"
    Ensure-WingetPackage -Id "Ollama.Ollama" -DisplayName "Ollama"
    Ensure-WingetPackage -Id "UB-Mannheim.TesseractOCR" -DisplayName "Tesseract OCR"
    Ensure-WingetPackage -Id "TheDocumentFoundation.LibreOffice" -DisplayName "LibreOffice"

    Ensure-BackendEnv
    Ensure-FrontendEnv
    Ensure-DockerDesktop
    Ensure-Postgres
    Ensure-Qdrant
    Ensure-Ollama
    Ensure-PythonEnvironment
    Verify-Cuda
    Verify-ModelCaches
    Verify-OcrAndOffice
    Ensure-NodeFrontend
    Ensure-CorpusConfiguration
    Run-Alembic
    Start-Application

    Write-Host ""
    Write-Host "CIAL Knowledge OS installation completed." -ForegroundColor Green
    Write-Host "Install log: $LogPath"
}
finally {
    Stop-Transcript | Out-Null
}
