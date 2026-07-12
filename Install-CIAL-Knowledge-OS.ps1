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
    [string]$TorchVersion = "2.13.0",
    [string]$TorchIndexUrl = "https://download.pytorch.org/whl/cu132",
    [int]$MinimumFreeDiskGB = 80,
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
$StatePath = Join-Path $StateRoot "install-state.json"
$ReportRoot = Join-Path $RepoRoot "outputs\installer\reports"
$AppConfigPath = Join-Path $RepoRoot "data\config\application.json"
$BackendEnvPath = Join-Path $BackendRoot "backend\.env"
$FrontendEnvPath = Join-Path $FrontendRoot ".env"
if ([string]::IsNullOrWhiteSpace($QdrantComposeFile)) {
    $QdrantComposeFile = Join-Path $BackendRoot "docker-compose.qdrant.yml"
}

$bootstrapIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
$bootstrapPrincipal = [Security.Principal.WindowsPrincipal]::new($bootstrapIdentity)
if (-not $bootstrapPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "CIAL Knowledge OS installation requires Administrator privileges." -ForegroundColor Red
    throw "Run Install-CIAL-Knowledge-OS.bat as Administrator."
}

New-Item -ItemType Directory -Force -Path $LogsRoot, $StateRoot, $ReportRoot | Out-Null
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$LogPath = Join-Path $LogsRoot "install-$Timestamp.log"
$ComponentLogsRoot = Join-Path $LogsRoot $Timestamp
New-Item -ItemType Directory -Force -Path $ComponentLogsRoot | Out-Null
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

function Get-InstallState {
    if (Test-Path -LiteralPath $StatePath -PathType Leaf) {
        try { return Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json }
        catch { Write-Host "Ignoring unreadable installer state: $StatePath" -ForegroundColor Yellow }
    }
    return [pscustomobject]@{ version = 2; completed_stages = @(); stages = [pscustomobject]@{}; reboot_required = $false; last_updated = $null }
}

function Save-InstallState {
    param([object]$State)
    $State.last_updated = (Get-Date).ToUniversalTime().ToString("o")
    $State | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $StatePath -Encoding UTF8
}

function Complete-InstallStage {
    param(
        [string]$Name,
        [ValidateSet("verified", "skipped", "installed", "repaired")][string]$Action = "verified",
        [hashtable]$Details = @{}
    )
    $state = Get-InstallState
    $state | Add-Member -NotePropertyName "version" -NotePropertyValue 2 -Force
    $completed = @($state.completed_stages)
    if ($Name -notin $completed) { $completed += $Name }
    $state.completed_stages = $completed
    if ($null -eq $state.stages) { $state | Add-Member -NotePropertyName "stages" -NotePropertyValue ([pscustomobject]@{}) -Force }
    $record = [ordered]@{ action=$Action; verified=$true; timestamp=(Get-Date).ToUniversalTime().ToString("o") }
    foreach ($key in $Details.Keys) { $record[$key] = $Details[$key] }
    $state.stages | Add-Member -NotePropertyName $Name -NotePropertyValue ([pscustomobject]$record) -Force
    $state.reboot_required = $false
    Save-InstallState $state
}

function Get-FilesFingerprint {
    param([string[]]$Paths, [string[]]$AdditionalValues = @())
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $builder = [Text.StringBuilder]::new()
        foreach ($path in $Paths) {
            if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { [void]$builder.AppendLine("MISSING:$path"); continue }
            [void]$builder.AppendLine((Resolve-Path -LiteralPath $path).Path)
            [void]$builder.AppendLine((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash)
        }
        foreach ($value in $AdditionalValues) { [void]$builder.AppendLine($value) }
        return ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($builder.ToString())))).Replace("-", "").ToLowerInvariant()
    } finally { $sha.Dispose() }
}

function Get-StageRecord {
    param([string]$Name)
    $state = Get-InstallState
    if ($null -eq $state.stages) { return $null }
    return $state.stages.PSObject.Properties[$Name].Value
}

function Register-ResumeAfterLogin {
    $runKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce"
    $resumeArguments = @('-NoProfile','-ExecutionPolicy','Bypass','-File',$PSCommandPath,'-BackendPort',"$BackendPort",'-FrontendPort',"$FrontendPort",'-PostgresPort',"$PostgresPort",'-PostgresContainerName',$PostgresContainerName,'-PostgresVolumeName',$PostgresVolumeName,'-QdrantComposeFile',$QdrantComposeFile,'-QdrantUrl',$QdrantUrl,'-OllamaModel',$OllamaModel,'-EmbeddingModel',$EmbeddingModel,'-RerankerModel',$RerankerModel,'-TorchVersion',$TorchVersion,'-TorchIndexUrl',$TorchIndexUrl,'-MinimumFreeDiskGB',"$MinimumFreeDiskGB")
    if (-not [string]::IsNullOrWhiteSpace($CorpusRepositoryPath)) { $resumeArguments += @('-CorpusRepositoryPath',$CorpusRepositoryPath) }
    if ($SkipPrerequisiteInstall) { $resumeArguments += '-SkipPrerequisiteInstall' }
    if ($SkipModelSmoke) { $resumeArguments += '-SkipModelSmoke' }
    if ($VerifyCleanFrontendInstall) { $resumeArguments += '-VerifyCleanFrontendInstall' }
    if ($NoBrowser) { $resumeArguments += '-NoBrowser' }
    $argumentLiteral = ($resumeArguments | ForEach-Object { "'" + ("$_".Replace("'", "''")) + "'" }) -join ','
    $resumeScript = "Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList @($argumentLiteral)"
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($resumeScript))
    $command = "powershell.exe -NoProfile -WindowStyle Hidden -EncodedCommand $encoded"
    New-Item -Path $runKey -Force | Out-Null
    New-ItemProperty -Path $runKey -Name "CIALKnowledgeOSInstallerResume" -Value $command -PropertyType String -Force | Out-Null
}

function Request-InstallerReboot {
    param([string]$Reason)
    $state = Get-InstallState
    $state.reboot_required = $true
    $state | Add-Member -NotePropertyName "reboot_reason" -NotePropertyValue $Reason -Force
    Save-InstallState $state
    Register-ResumeAfterLogin
    Write-Host "A Windows restart is required: $Reason" -ForegroundColor Yellow
    Write-Host "The installer registered a one-time resume at next login. Rerunning the BAT also resumes safely."
    exit 3010
}

function Test-InternetConnectivity {
    foreach ($uri in @("https://api.github.com", "https://pypi.org", "https://registry.npmjs.org")) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Method Head -Uri $uri -TimeoutSec 15
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) { return $true }
        } catch { }
    }
    return $false
}

function Assert-RepositoryStructure {
    $required = @(
        "Install-CIAL-Knowledge-OS.bat", "Launch-CIAL-Knowledge-OS.ps1",
        "services\knowledge-engine\requirements.txt", "services\knowledge-engine\alembic.ini",
        "services\knowledge-engine\backend\app\main.py", "services\knowledge-engine\docker-compose.qdrant.yml",
        "frontend\package.json", "frontend\pnpm-lock.yaml", "scripts\configure_corpus_repository.ps1"
    )
    $missing = @($required | Where-Object { -not (Test-Path -LiteralPath (Join-Path $RepoRoot $_)) })
    if ($missing.Count -gt 0) { Stop-Install "Repository is incomplete. Missing: $($missing -join ', ')" }
}

function Invoke-Preflight {
    Write-Step "Preflight"
    if (-not (Test-Administrator)) { Stop-Install "Run Install-CIAL-Knowledge-OS.bat as Administrator." }
    Assert-RepositoryStructure
    $os = Get-CimInstance Win32_OperatingSystem
    if ([Environment]::OSVersion.Version.Build -lt 22000) { Stop-Install "Windows 11 (build 22000 or newer) is required." }
    if (-not [Environment]::Is64BitOperatingSystem) { Stop-Install "64-bit Windows is required." }
    $drive = Get-PSDrive -Name ([IO.Path]::GetPathRoot($RepoRoot).TrimEnd(':','\'))
    $freeGB = [math]::Round($drive.Free / 1GB, 1)
    if ($freeGB -lt $MinimumFreeDiskGB) { Stop-Install "At least $MinimumFreeDiskGB GB free is required; $freeGB GB is available." }
    if (-not (Test-InternetConnectivity)) { Stop-Install "Internet connectivity to package registries is required for first installation." }
    $gpu = Get-CimInstance Win32_VideoController | Where-Object { $_.Name -match "NVIDIA" } | Select-Object -First 1
    if ($null -eq $gpu) { Stop-Install "No NVIDIA GPU was detected. CUDA-enabled installation cannot continue." }
    $cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
    if ($cpu.VirtualizationFirmwareEnabled -eq $false) { Stop-Install "Hardware virtualization is disabled in firmware. Enable it before installing Docker Desktop." }
    Write-Host "Windows: $($os.Caption) $($os.Version); architecture=$env:PROCESSOR_ARCHITECTURE"
    Write-Host "Free disk: $freeGB GB; virtualization firmware enabled=$($cpu.VirtualizationFirmwareEnabled)"
    Write-Host "NVIDIA GPU: $($gpu.Name); driver=$($gpu.DriverVersion)"
    Write-Host "Repository: $RepoRoot; state=$StatePath"
    $priorState = Get-InstallState
    Write-Host "Previously completed stages: $(@($priorState.completed_stages) -join ', ')"
    Complete-InstallStage "preflight" -Action "verified" -Details @{ windows=$os.Caption; build=$os.BuildNumber; architecture=$env:PROCESSOR_ARCHITECTURE; free_disk_gb=$freeGB; gpu=$gpu.Name; driver=$gpu.DriverVersion; virtualization=$cpu.VirtualizationFirmwareEnabled; repository=$RepoRoot }
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

function Invoke-ComponentCommand {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$LogName,
        [string]$WorkingDirectory = $RepoRoot,
        [string]$FailureMessage = "Component command failed."
    )
    $previous = (Get-Location).ProviderPath
    try {
        Set-Location -LiteralPath $WorkingDirectory
        $output = & $FilePath @Arguments 2>&1
        $exitCode = $LASTEXITCODE
        $output | Set-Content -LiteralPath (Join-Path $ComponentLogsRoot $LogName) -Encoding UTF8
        $output | ForEach-Object { Write-Host "$_" }
        if ($exitCode -ne 0) { Stop-Install "$FailureMessage See $(Join-Path $ComponentLogsRoot $LogName)." }
    } finally { Set-Location -LiteralPath $previous }
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
        $nodeVersion = $nodeCheck.Version -replace '^v',''
        $nodeParts = $nodeVersion.Split('.')
        $nodeMajor = [int]$nodeParts[0]
        $nodeMinor = if ($nodeParts.Count -gt 1) { [int]$nodeParts[1] } else { 0 }
        $nodeSupported = $nodeMajor -gt 20 -or ($nodeMajor -eq 20 -and $nodeMinor -ge 19)
        if (-not $nodeSupported) {
            Write-Host "Ignoring unsupported Node candidate $node ($($nodeCheck.Version)); Node >=20.19 is required."
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
        if (($pnpmCheck.Version -replace '^v','').Trim() -ne $requiredPnpmVersion) {
            Stop-Install "Resolved pnpm version '$($pnpmCheck.Version)' does not match required $requiredPnpmVersion."
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
    $health = Test-PrerequisitePackage -Id $Id
    if ($health.Healthy) {
        Write-Host "$DisplayName is healthy: $($health.Path) $($health.Version)"
        Complete-InstallStage "prerequisite-$Id" -Action "skipped" -Details @{ path=$health.Path; version=$health.Version }
        return
    }
    if ($SkipPrerequisiteInstall) { Stop-Install "$DisplayName is missing or invalid and prerequisite installation was disabled: $($health.Reason)" }
    $winget = Get-CommandPath "winget.exe"
    if ($null -eq $winget) {
        Stop-Install "winget is required to install missing prerequisites automatically. Install App Installer from Microsoft Store or rerun with prerequisites installed."
    }
    Write-Host "Verifying/installing $DisplayName ($Id) via winget."
    & $winget list --id $Id --exact --accept-source-agreements | Out-Null
    $wasInstalled = $LASTEXITCODE -eq 0
    $installArguments = @("install", "--id", $Id, "--exact", "--silent", "--accept-package-agreements", "--accept-source-agreements")
    if ($wasInstalled) { $installArguments += "--force" }
    & $winget @installArguments
    if ($LASTEXITCODE -in @(3010, -1978335189)) {
        Request-InstallerReboot "$DisplayName installation requires a restart."
    }
    if ($LASTEXITCODE -ne 0) {
        Stop-Install "winget could not install $DisplayName ($Id). Install it manually and rerun."
    }
    Refresh-ProcessPath
    $health = Test-PrerequisitePackage -Id $Id
    if (-not $health.Healthy) {
        if ($Id -eq "Docker.DockerDesktop") { Request-InstallerReboot "Docker Desktop installation must finish after restart." }
        Stop-Install "$DisplayName installation completed but validation failed: $($health.Reason)"
    }
    Complete-InstallStage "prerequisite-$Id" -Action $(if ($wasInstalled) { "repaired" } else { "installed" }) -Details @{ path=$health.Path; version=$health.Version }
}

function Test-PrerequisitePackage {
    param([string]$Id)
    $result = [ordered]@{ Healthy=$false; Path=""; Version=""; Reason="not detected" }
    switch ($Id) {
        "Git.Git" {
            $path=Get-CommandPath "git.exe"; if($path){$v=Invoke-Capture $path @("--version");$result.Path=$path;$result.Version=$v.Output;$result.Healthy=$v.ExitCode -eq 0}
        }
        "Python.Python.3.11" {
            $path=Get-CommandPath "py.exe"; if($path){$v=Invoke-Capture $path @("-3.11","-c","import sys; print(sys.executable); print(sys.version.split()[0]); raise SystemExit(0 if sys.version_info[:2]==(3,11) and sys.implementation.name=='cpython' else 1)");$lines=$v.Output -split "`n";$pythonPath=$lines[0].Trim();$company=if(Test-Path $pythonPath){(Get-Item $pythonPath).VersionInfo.CompanyName}else{""};$result.Path=$pythonPath;$result.Version=if($lines.Count -gt 1){$lines[1]}else{""};$result.Healthy=$v.ExitCode -eq 0 -and $company -match "Python Software Foundation"}
        }
        "OpenJS.NodeJS.LTS" {
            $path=Get-OfficialNodePath; if(Test-Path -LiteralPath $path -PathType Leaf){$v=Invoke-Capture $path @("--version");$parts=(($v.Output -replace '^v','').Split('.'));$major=[int]$parts[0];$minor=if($parts.Count -gt 1){[int]$parts[1]}else{0};$result.Path=$path;$result.Version=$v.Output;$result.Healthy=$v.ExitCode -eq 0 -and ($major -gt 20 -or ($major -eq 20 -and $minor -ge 19))}
        }
        "Docker.DockerDesktop" {
            $path=Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe";$result.Path=$path;$result.Healthy=Test-Path -LiteralPath $path -PathType Leaf;$result.Version=if($result.Healthy){(Get-Item $path).VersionInfo.ProductVersion}else{""}
        }
        "Ollama.Ollama" {
            $path=Get-CommandPath "ollama.exe";if(-not $path){$candidate=Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe";if(Test-Path $candidate){$path=$candidate}};if($path){$v=Invoke-Capture $path @("--version");$result.Path=$path;$result.Version=$v.Output;$result.Healthy=$v.ExitCode -eq 0}
        }
        "UB-Mannheim.TesseractOCR" {
            $path=Join-Path $env:ProgramFiles "Tesseract-OCR\tesseract.exe";if(Test-Path $path){$v=Invoke-Capture $path @("--version");$result.Path=$path;$result.Version=($v.Output -split "`n")[0];$result.Healthy=$v.ExitCode -eq 0}
        }
        "TheDocumentFoundation.LibreOffice" {
            $path=Join-Path $env:ProgramFiles "LibreOffice\program\soffice.exe";if(Test-Path $path){$v=Invoke-Capture $path @("--version");$result.Path=$path;$result.Version=$v.Output;$result.Healthy=$v.ExitCode -eq 0}
        }
        "Microsoft.VCRedist.2015+.x64" {
            $key="HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64";if(Test-Path $key){$item=Get-ItemProperty $key;$result.Path=$key;$result.Version=$item.Version;$result.Healthy=$item.Installed -eq 1}
        }
    }
    if (-not $result.Healthy) { $result.Reason="missing, unusable, or unsupported version" }
    return [pscustomobject]$result
}

function Verify-PrerequisiteExecutables {
    Refresh-ProcessPath
    $checks = @(
        @{ Label="Git"; Name="git.exe" }, @{ Label="Python launcher"; Name="py.exe" },
        @{ Label="Docker"; Name="docker.exe" }, @{ Label="Ollama"; Name="ollama.exe" }
    )
    foreach ($check in $checks) {
        $path = Get-CommandPath $check.Name
        if ($null -eq $path) {
            if ($check.Name -eq "docker.exe") { Request-InstallerReboot "Docker Desktop installation requires Windows to refresh its components." }
            Stop-Install "$($check.Label) was installed but its executable is unavailable."
        }
        $version = Test-ExecutableVersion -Label $check.Label -FilePath $path
        if (-not $version.Ok) { Stop-Install $version.Error }
        Write-Host "$($check.Label): $path ($($version.Version))"
    }
}

function Resolve-DockerComposeTool {
    $docker = Get-CommandPath "docker.exe"
    if ($null -ne $docker) {
        $plugin = Invoke-Capture -FilePath $docker -Arguments @("compose", "version")
        if ($plugin.ExitCode -eq 0) { return [pscustomobject]@{ File=$docker; Prefix=@("compose") } }
    }
    foreach ($candidate in @(
        (Join-Path $env:ProgramFiles "Docker\Docker\resources\bin\docker-compose.exe"),
        (Join-Path $env:ProgramFiles "Docker\cli-plugins\docker-compose.exe")
    )) {
        $check = Test-ExecutableVersion -Label "Docker Compose" -FilePath $candidate
        if ($check.Ok) { Write-Host "Docker Compose: $candidate ($($check.Version))"; return [pscustomobject]@{ File=$candidate; Prefix=@() } }
    }
    Stop-Install "Docker Compose is unavailable after Docker Desktop installation."
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

function Get-PortProcessId {
    param([int]$Port)
    foreach ($line in (netstat -ano | Select-String ":$Port\s")) {
        $parts = ($line.Line -split "\s+") | Where-Object { $_ }
        if ($parts.Length -ge 5 -and $parts[1] -match ":$Port$" -and $parts[3] -eq "LISTENING") { return [int]$parts[-1] }
    }
    return $null
}

function Stop-ExistingCialFrontendForInstall {
    $pidAtPort = Get-PortProcessId -Port $FrontendPort
    if ($null -eq $pidAtPort) { return }
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$FrontendPort/login" -TimeoutSec 5
        if ($response.StatusCode -ne 200 -or $response.Content -notmatch "CIAL Knowledge OS") {
            Stop-Install "Port $FrontendPort is occupied by process $pidAtPort and is not the CIAL frontend."
        }
    } catch { Stop-Install "Port $FrontendPort is occupied by process $pidAtPort and could not be identified as CIAL." }
    Write-Host "Stopping the existing CIAL frontend process $pidAtPort before rebuilding."
    Stop-Process -Id $pidAtPort -Force
    Start-Sleep -Seconds 2
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

function Set-EnvFileDefaults {
    param([string]$Path, [hashtable]$Values)
    $existing = Get-EnvMap -Paths @($Path)
    $missing = @{}
    foreach ($key in $Values.Keys) {
        if (-not $existing.ContainsKey($key) -or [string]::IsNullOrWhiteSpace($existing[$key])) {
            $missing[$key] = $Values[$key]
        }
    }
    if ($missing.Count -gt 0) { Set-EnvFileValue -Path $Path -Values $missing }
}

function Get-DatabaseUrl {
    $map = Get-EnvMap -Paths @((Join-Path $RepoRoot ".env"), (Join-Path $BackendRoot ".env"), $BackendEnvPath)
    if ($map.ContainsKey("DATABASE_URL") -and -not [string]::IsNullOrWhiteSpace($map["DATABASE_URL"]) -and $map["DATABASE_URL"] -notmatch "<PASSWORD>") {
        return $map["DATABASE_URL"]
    }
    return $null
}

function New-Password {
    $bytes = New-Object byte[] 24
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()

    try {
        $rng.GetBytes($bytes)
    }
    finally {
        $rng.Dispose()
    }

    return ([Convert]::ToBase64String($bytes).TrimEnd("=") -replace "[+/]", "A")
}

function Protect-SecretFile {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return }
    try {
        $acl = Get-Acl -LiteralPath $Path
        $acl.SetAccessRuleProtection($true, $false)
        foreach ($rule in @($acl.Access)) { $acl.RemoveAccessRuleAll($rule) | Out-Null }
        $rights = [Security.AccessControl.FileSystemRights]::FullControl
        $inheritance = [Security.AccessControl.InheritanceFlags]::None
        $propagation = [Security.AccessControl.PropagationFlags]::None
        $allow = [Security.AccessControl.AccessControlType]::Allow
        foreach ($identity in @([Security.Principal.WindowsIdentity]::GetCurrent().Name, "BUILTIN\Administrators", "NT AUTHORITY\SYSTEM")) {
            $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($identity, $rights, $inheritance, $propagation, $allow))
        }
        Set-Acl -LiteralPath $Path -AclObject $acl
    } catch { Stop-Install "Could not restrict access to secret file ${Path}: $($_.Exception.Message)" }
}

function Ensure-BackendEnv {
    Write-Step "Preparing backend environment file"
    $script:GeneratedPostgresCredential = $false
    if (-not (Test-Path -LiteralPath $BackendEnvPath -PathType Leaf)) {
        Copy-Item -LiteralPath (Join-Path $BackendRoot "backend\.env.example") -Destination $BackendEnvPath
    }
    $databaseUrl = Get-DatabaseUrl
    if ([string]::IsNullOrWhiteSpace($databaseUrl)) {
        $passwordPath = Join-Path $StateRoot "postgres-password.txt"
        if (Test-Path -LiteralPath $passwordPath -PathType Leaf) {
            $password = (Get-Content -LiteralPath $passwordPath -Raw).Trim()
            if ([string]::IsNullOrWhiteSpace($password)) { Stop-Install "Installer-managed PostgreSQL credential file is empty. It was not replaced because an existing volume may depend on it." }
            Write-Host "Reusing preserved installer-managed PostgreSQL credentials."
        } else {
            $password = New-Password
            $script:GeneratedPostgresCredential = $true
            Set-Content -LiteralPath $passwordPath -Value $password -Encoding UTF8
            Protect-SecretFile -Path $passwordPath
            Write-Host "Generated PostgreSQL credentials and stored them under outputs\installer\runtime."
        }
        $databaseUrl = "postgresql+psycopg://postgres:$password@localhost:$PostgresPort/cial_knowledge_os_dev"
    }
    Set-EnvFileValue -Path $BackendEnvPath -Values @{ "DATABASE_URL" = $databaseUrl }
    $authSecret = New-Password
    Set-EnvFileDefaults -Path $BackendEnvPath -Values @{
        "CIAL_AUTO_INDEX_ON_STARTUP" = "true"
        "CIAL_FORCE_REBUILD_ON_STARTUP" = "false"
        "CIAL_STARTUP_INDEX_TIMEOUT_SECONDS" = "0"
        "CIAL_APP_DATA_DIR" = "data"
        "CIAL_OUTPUTS_DIR" = "outputs"
        "CIAL_MODELS_DIR" = "models"
        "DATABASE_URL" = $databaseUrl
        "CIAL_AUTH_SECRET_KEY" = $authSecret
        "CIAL_CORPUS_SYNC_ON_STARTUP" = "true"
        "CIAL_CORPUS_WATCH" = "false"
        "CIAL_QDRANT_MODE" = "server"
        "CIAL_QDRANT_URL" = $QdrantUrl
        "CIAL_QDRANT_BATCH_SIZE" = "32"
        "CIAL_QDRANT_UPSERT_WAIT" = "true"
        "CIAL_OLLAMA_MODEL_NAME" = $OllamaModel
        "CIAL_OLLAMA_BASE_URL" = "http://127.0.0.1:11434"
        "CIAL_EMBEDDING_MODEL_NAME" = $EmbeddingModel
        "CIAL_RERANKER_MODEL_NAME" = $RerankerModel
        "CIAL_RERANKER_DEVICE" = "auto"
        "CIAL_RERANKER_BATCH_SIZE" = "16"
        "CIAL_LOCAL_FILES_ONLY" = "true"
        "TRANSFORMERS_OFFLINE" = "1"
        "HF_HUB_OFFLINE" = "1"
    }
    Set-EnvFileValue -Path $BackendEnvPath -Values @{
        "CIAL_AUTO_INDEX_ON_STARTUP"="true"; "CIAL_FORCE_REBUILD_ON_STARTUP"="false"; "CIAL_STARTUP_INDEX_TIMEOUT_SECONDS"="0"
        "CIAL_APP_DATA_DIR"="data"; "CIAL_OUTPUTS_DIR"="outputs"; "CIAL_MODELS_DIR"="models"
        "CIAL_CORPUS_SYNC_ON_STARTUP"="true"; "CIAL_CORPUS_WATCH"="false"
        "CIAL_QDRANT_MODE"="server"; "CIAL_QDRANT_URL"=$QdrantUrl; "CIAL_QDRANT_BATCH_SIZE"="32"; "CIAL_QDRANT_UPSERT_WAIT"="true"
        "CIAL_OLLAMA_MODEL_NAME"=$OllamaModel; "CIAL_OLLAMA_BASE_URL"="http://127.0.0.1:11434"
        "CIAL_EMBEDDING_MODEL_NAME"=$EmbeddingModel; "CIAL_RERANKER_MODEL_NAME"=$RerankerModel; "CIAL_RERANKER_DEVICE"="auto"; "CIAL_RERANKER_BATCH_SIZE"="16"
    }
    Write-Host "Backend .env prepared. DATABASE_URL value was not printed."
    Protect-SecretFile -Path $BackendEnvPath
}

function Ensure-FrontendEnv {
    Write-Step "Preparing frontend environment file"
    if (-not (Test-Path -LiteralPath $FrontendEnvPath -PathType Leaf)) {
        Copy-Item -LiteralPath (Join-Path $FrontendRoot ".env.example") -Destination $FrontendEnvPath
    }
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
        Request-InstallerReboot "Docker Desktop was installed but docker.exe is not visible yet."
    }
    & $docker info | Out-Null
    if ($LASTEXITCODE -eq 0) {
        (& $docker version 2>&1) | Set-Content -LiteralPath (Join-Path $ComponentLogsRoot "docker.log") -Encoding UTF8
        Complete-InstallStage "docker" -Action "skipped" -Details @{ executable=$docker; status="running" }
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
            (& $docker version 2>&1) | Set-Content -LiteralPath (Join-Path $ComponentLogsRoot "docker.log") -Encoding UTF8
            Complete-InstallStage "docker" -Action "repaired" -Details @{ executable=$docker; status="started" }
            return
        }
    } while ((Get-Date) -lt $deadline)
    $rebootSignals = @(
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending",
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired"
    )
    if ($rebootSignals | Where-Object { Test-Path $_ }) { Request-InstallerReboot "Windows or Docker Desktop requires a restart." }
    Stop-Install "Docker Desktop did not become ready. Review Docker/WSL virtualization status in the installer log."
}

function Ensure-Postgres {
    Write-Step "Starting PostgreSQL"
    $script:PostgresAction = "skipped"
    $docker = Get-CommandPath "docker.exe"
    $databaseUrl = Get-DatabaseUrl
    if ($databaseUrl -match "@([^:/]+):(\d+)/") {
        $hostName = $Matches[1]
        $port = [int]$Matches[2]
        if (($hostName -in @("localhost", "127.0.0.1")) -and (Test-PortOpen -HostName "127.0.0.1" -Port $port)) {
            Write-Host "A service is listening at ${hostName}:$port; credentials will be verified after Python setup."
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
        $volumeExists = ((& $docker volume ls --format "{{.Name}}") -contains $PostgresVolumeName)
        if ($volumeExists -and $script:GeneratedPostgresCredential) {
            Stop-Install "PostgreSQL volume '$PostgresVolumeName' already exists without its managed container, but no matching preserved credentials were found. The volume was not mounted, changed, or deleted. Restore its DATABASE_URL/credential file or choose a new explicitly named container and volume."
        }
        & $docker run -d --name $PostgresContainerName `
            -e POSTGRES_USER=postgres `
            -e POSTGRES_PASSWORD=$password `
            -e POSTGRES_DB=cial_knowledge_os_dev `
            -p "$PostgresPort`:5432" `
            -v "$PostgresVolumeName`:/var/lib/postgresql/data" `
            postgres:18 | Out-Null
        if ($LASTEXITCODE -ne 0) { Stop-Install "PostgreSQL container creation failed. Check for a port conflict or Docker error." }
        $script:PostgresAction = "installed"
    }
    else {
        $containerRunning = ((& $docker ps --format "{{.Names}}") -contains $PostgresContainerName)
        if (-not $containerRunning) {
            & $docker start $PostgresContainerName | Out-Null
            if ($LASTEXITCODE -ne 0) { Stop-Install "Existing PostgreSQL container could not be started; no data was changed." }
            $script:PostgresAction = "repaired"
        }
    }
    $deadline = (Get-Date).AddMinutes(2)
    do {
        Start-Sleep -Seconds 3
        if (Test-PortOpen -HostName "127.0.0.1" -Port $PostgresPort) { return }
    } while ((Get-Date) -lt $deadline)
    Stop-Install "PostgreSQL did not become reachable on port $PostgresPort."
}

function Verify-PostgresConnection {
    Write-Step "Verifying PostgreSQL credentials and database"
    $script = @"
import os
from sqlalchemy import create_engine, text
from backend.app.core.config import settings
engine = create_engine(settings.database_url, pool_pre_ping=True)
with engine.connect() as connection:
    assert connection.execute(text("SELECT 1")).scalar_one() == 1
    database = connection.execute(text("SELECT current_database()")).scalar_one()
    user = connection.execute(text("SELECT current_user")).scalar_one()
    assert database == "cial_knowledge_os_dev", f"unexpected database: {database}"
    can_connect = connection.execute(text("SELECT has_database_privilege(current_user, current_database(), 'CONNECT')")).scalar_one()
    can_use_schema = connection.execute(text("SELECT has_schema_privilege(current_user, 'public', 'USAGE')")).scalar_one()
    assert can_connect and can_use_schema, "application user lacks database/schema access"
    print(f"database={database}; user={user}; select_1=ok; connect={can_connect}; schema_usage={can_use_schema}")
engine.dispose()
"@
    $previousPythonPath = $env:PYTHONPATH
    $env:PYTHONPATH = "$BackendRoot;$BackendRoot\src"
    try { $databaseOutput = $script | & $PythonExe - 2>&1; $databaseExit = $LASTEXITCODE }
    finally { $env:PYTHONPATH = $previousPythonPath }
    $safeDatabaseOutput = @($databaseOutput | ForEach-Object { "$_" -replace '(?i)postgresql\+psycopg://[^\s@]+@','postgresql+psycopg://<redacted>@' })
    $safeDatabaseOutput | Set-Content -LiteralPath (Join-Path $ComponentLogsRoot "postgresql.log") -Encoding UTF8
    $safeDatabaseOutput | ForEach-Object { Write-Host "$_" }
    if ($databaseExit -ne 0) {
        $owner = Get-PortProcessId -Port $PostgresPort
        Stop-Install "PostgreSQL connection failed on port $PostgresPort (owning PID: $owner). Existing volume credentials may differ from DATABASE_URL, or the listener may be unrelated. No process or data was changed; update DATABASE_URL to valid existing credentials or resolve the port conflict."
    }
    Complete-InstallStage "postgresql" -Action $script:PostgresAction -Details @{ container=$PostgresContainerName; volume=$PostgresVolumeName; database="cial_knowledge_os_dev"; sql_validation="ok" }
}

function Ensure-Qdrant {
    Write-Step "Starting Qdrant"
    if (-not (Test-Path -LiteralPath $QdrantComposeFile -PathType Leaf)) {
        Stop-Install "Qdrant compose file was not found: $QdrantComposeFile"
    }
    $existingQdrant = ((& docker.exe ps -a --format "{{.Names}}") -contains "cial-knowledge-os-v1-dev-qdrant")
    $qdrantAction = "skipped"
    if ($existingQdrant) {
        $qdrantRunning = ((& docker.exe ps --format "{{.Names}}") -contains "cial-knowledge-os-v1-dev-qdrant")
        if (-not $qdrantRunning) {
            Write-Host "Preserving the existing Qdrant container and storage; starting it without image replacement."
            & docker.exe start "cial-knowledge-os-v1-dev-qdrant" | Out-Null
            if ($LASTEXITCODE -ne 0) { Stop-Install "Existing Qdrant container could not be started." }
            $qdrantAction = "repaired"
        }
    } else {
        $compose = Resolve-DockerComposeTool
        Invoke-Logged -FilePath $compose.File -Arguments @($compose.Prefix + @("-f", $QdrantComposeFile, "up", "-d")) -WorkingDirectory $BackendRoot -FailureMessage "Qdrant compose startup failed."
        $qdrantAction = "installed"
    }
    if (-not (Wait-Url -Url "$QdrantUrl/collections" -Seconds 90)) {
        $owner = Get-PortProcessId -Port ([uri]$QdrantUrl).Port
        Stop-Install "Qdrant did not become ready at $QdrantUrl (port owner PID: $owner). Unrelated processes were not stopped."
    }
    try {
        $identity = (Invoke-WebRequest -UseBasicParsing -Uri "$QdrantUrl/" -TimeoutSec 10).Content | ConvertFrom-Json
        $version = [version]$identity.version
        if ($identity.title -notmatch "qdrant" -or $version.Major -ne 1 -or $version.Minor -lt 15 -or $version.Minor -gt 18) {
            Stop-Install "Service at $QdrantUrl is not a supported Qdrant 1.15-1.18 server (reported title='$($identity.title)', version='$($identity.version)'). Existing data was not modified."
        }
        $identity | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $ComponentLogsRoot "qdrant.log") -Encoding UTF8
        Complete-InstallStage "qdrant" -Action $qdrantAction -Details @{ url=$QdrantUrl; version=$identity.version; container="cial-knowledge-os-v1-dev-qdrant" }
    } catch { Stop-Install "Qdrant identity/version verification failed at ${QdrantUrl}: $($_.Exception.Message)" }
}

function Ensure-Ollama {
    Write-Step "Starting Ollama and verifying model"
    $ollama = Get-CommandPath "ollama.exe"
    if ($null -eq $ollama) {
        $candidate = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { $ollama = $candidate }
    }
    if ($null -eq $ollama) {
        Stop-Install "Ollama was not found after prerequisite installation. Restart the terminal or install Ollama manually."
    }
    $apiReady = $false
    try {
        $tagsResponse = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 5
        $tagsJson = $tagsResponse.Content | ConvertFrom-Json
        $apiReady = $tagsResponse.StatusCode -eq 200 -and $null -ne $tagsJson.models
    } catch { }
    if (-not $apiReady) {
        if (Test-PortOpen -HostName "127.0.0.1" -Port 11434) { Stop-Install "Port 11434 is occupied by a service that is not the Ollama API. It was not stopped." }
        Start-Process -FilePath $ollama -ArgumentList "serve" -WindowStyle Hidden
    }
    if (-not (Wait-Url -Url "http://127.0.0.1:11434/api/tags" -Seconds 90)) {
        Stop-Install "Ollama did not become ready at http://127.0.0.1:11434."
    }
    $models = (& $ollama list) -join "`n"
    $modelNames = @($models -split "`r?`n" | Select-Object -Skip 1 | ForEach-Object { ($_ -split "\s+")[0] })
    $action = "skipped"
    if ($OllamaModel -notin $modelNames) {
        Write-Host "Downloading required Ollama model $OllamaModel. This can take a long time."
        $pulled = $false
        foreach ($attempt in 1..3) {
            & $ollama pull $OllamaModel 2>&1 | Tee-Object -FilePath (Join-Path $ComponentLogsRoot "ollama-model-download.log")
            $pullExit = $LASTEXITCODE
            if ($pullExit -eq 0) { $pulled = $true; break }
            Write-Host "Ollama pull attempt $attempt failed; retrying." -ForegroundColor Yellow
            Start-Sleep -Seconds (5 * $attempt)
        }
        if (-not $pulled) { Stop-Install "Ollama could not download '$OllamaModel' after three attempts." }
        $action = "installed"
    }
    $details = & $ollama show $OllamaModel 2>&1
    if ($LASTEXITCODE -ne 0) { Stop-Install "Ollama model '$OllamaModel' failed post-download verification." }
    Write-Host ($details | Select-Object -First 12)
    $details | Set-Content -LiteralPath (Join-Path $ComponentLogsRoot "ollama-model-verification.log") -Encoding UTF8
    Complete-InstallStage "ollama" -Action $action -Details @{ executable=$ollama; model=$OllamaModel; api="http://127.0.0.1:11434" }
}

function Ensure-PythonEnvironment {
    Write-Step "Creating Python 3.11 virtual environment"
    $venvAction = "skipped"
    if (Test-Path -LiteralPath $PythonExe -PathType Leaf) {
        & $PythonExe -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,11) else 1)"
        $versionOk = $LASTEXITCODE -eq 0
        & $PythonExe -m pip --version | Out-Null
        $pipOk = $LASTEXITCODE -eq 0
        if (-not $versionOk -or -not $pipOk) {
            $invalidVenv = "$VenvRoot.invalid-$(Get-Date -Format 'yyyyMMddHHmmss')"
            $resolvedVenv = (Resolve-Path -LiteralPath $VenvRoot).Path
            $resolvedRepo = (Resolve-Path -LiteralPath $RepoRoot).Path
            if (-not $resolvedVenv.StartsWith($resolvedRepo, [StringComparison]::OrdinalIgnoreCase) -or -not ([IO.Path]::GetFullPath($invalidVenv)).StartsWith($resolvedRepo, [StringComparison]::OrdinalIgnoreCase)) {
                Stop-Install "Refusing to move an invalid virtual environment outside the repository."
            }
            Write-Host "Preserving invalid virtual environment at $invalidVenv"
            Move-Item -LiteralPath $VenvRoot -Destination $invalidVenv
            $venvAction = "repaired"
        }
    }
    $py = Get-CommandPath "py.exe"
    if ($null -ne $py) {
        & $py -3.11 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,11) else 1)"
        if ($LASTEXITCODE -ne 0) { Stop-Install "Python 3.11 launcher exists but Python 3.11 is unavailable." }
        if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
            Invoke-Logged -FilePath $py -Arguments @("-3.11", "-m", "venv", $VenvRoot) -FailureMessage "Could not create Python 3.11 virtual environment."
            if ($venvAction -ne "repaired") { $venvAction = "installed" }
        }
    }
    else {
        $python = Get-CommandPath "python.exe"
        if ($null -eq $python) { Stop-Install "Python was not found after prerequisite installation." }
        & $python -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,11) else 1)"
        if ($LASTEXITCODE -ne 0) { Stop-Install "python.exe is not Python 3.11. Install Python 3.11 and rerun." }
        if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
            Invoke-Logged -FilePath $python -Arguments @("-m", "venv", $VenvRoot) -FailureMessage "Could not create Python 3.11 virtual environment."
            if ($venvAction -ne "repaired") { $venvAction = "installed" }
        }
    }
    # -----------------------------------------------------------------------------
    # Verify Python packaging tools.
    # Use Invoke-Capture instead of a direct invocation so Windows PowerShell 5.1
    # does not terminate the installer on expected stderr output.
    # -----------------------------------------------------------------------------

    $probe = Invoke-Capture `
        -FilePath $PythonExe `
        -Arguments @(
            "-c",
            "import setuptools; import pip; import wheel"
        )

    if ($probe.ExitCode -ne 0) {

        Write-Step "Repairing Python packaging tools"

        Invoke-Logged `
            -FilePath $PythonExe `
            -Arguments @(
                "-m",
                "ensurepip",
                "--upgrade"
            ) `
            -FailureMessage "ensurepip failed."

        Invoke-Logged `
            -FilePath $PythonExe `
            -Arguments @(
                "-m",
                "pip",
                "install",
                "--upgrade",
                "--force-reinstall",
                "pip",
                "setuptools",
                "wheel"
            ) `
            -FailureMessage "Python packaging tool repair failed."

        $probe = Invoke-Capture `
            -FilePath $PythonExe `
            -Arguments @(
                "-c",
                "import setuptools; import pip; import wheel"
            )

        if ($probe.ExitCode -ne 0) {

            Write-Warning "Existing virtual environment appears corrupted."

            $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
            $backupVenv = "$VenvRoot.broken-$timestamp"

            if (Test-Path -LiteralPath $VenvRoot) {
                Rename-Item `
                    -LiteralPath $VenvRoot `
                    -NewName (Split-Path $backupVenv -Leaf)
            }

            Write-Step "Recreating Python 3.11 virtual environment"

            if ($null -ne $py) {
                Invoke-Logged `
                    -FilePath $py `
                    -Arguments @(
                        "-3.11",
                        "-m",
                        "venv",
                        $VenvRoot
                    ) `
                    -FailureMessage "Failed to recreate Python 3.11 virtual environment."
            }
            else {
                Invoke-Logged `
                    -FilePath $python `
                    -Arguments @(
                        "-m",
                        "venv",
                        $VenvRoot
                    ) `
                    -FailureMessage "Failed to recreate Python 3.11 virtual environment."
            }

            $PythonExe = Join-Path $VenvRoot "Scripts\python.exe"

            Invoke-Logged `
                -FilePath $PythonExe `
                -Arguments @(
                    "-m",
                    "ensurepip",
                    "--upgrade"
                ) `
                -FailureMessage "ensurepip failed after recreating the virtual environment."

            Invoke-Logged `
                -FilePath $PythonExe `
                -Arguments @(
                    "-m",
                    "pip",
                    "install",
                    "--upgrade",
                    "pip",
                    "setuptools",
                    "wheel"
                ) `
                -FailureMessage "Failed to initialize packaging tools in the recreated virtual environment."

            $probe = Invoke-Capture `
                -FilePath $PythonExe `
                -Arguments @(
                    "-c",
                    "import setuptools; import pip; import wheel"
                )

            if ($probe.ExitCode -ne 0) {
                Stop-Install "Python packaging tools remain unhealthy after recreating the virtual environment."
            }

            $venvAction = "repaired"
        }
        elseif ($venvAction -eq "skipped") {
            $venvAction = "repaired"
        }
    }
    $pythonVersion = (& $PythonExe -c "import sys; print(sys.version.split()[0])").Trim()
    Complete-InstallStage "python-environment" -Action $venvAction -Details @{ python=$PythonExe; version=$pythonVersion }
}

function Test-CudaTorch {
    $code = "import torch,sys; ok=torch.__version__.split('+')[0]=='$TorchVersion' and bool(torch.version.cuda) and torch.cuda.is_available() and torch.cuda.device_count()>0; print(torch.__version__,torch.version.cuda,torch.cuda.device_count()); sys.exit(0 if ok else 1)"
    $result = Invoke-Capture -FilePath $PythonExe -Arguments @("-c", $code)
    return $result.ExitCode -eq 0
}

function Ensure-CudaTorch {
    Write-Step "Checking CUDA PyTorch"
    $action = "skipped"
    if (-not (Test-CudaTorch)) {
        $installed = Invoke-Capture -FilePath $PythonExe -Arguments @("-m", "pip", "show", "torch")
        if ($installed.ExitCode -eq 0) {
            Invoke-Logged -FilePath $PythonExe -Arguments @("-m", "pip", "uninstall", "-y", "torch", "torchvision", "torchaudio") -FailureMessage "Conflicting Torch packages could not be removed safely."
            $action = "repaired"
        } else { $action = "installed" }
        Invoke-ComponentCommand -FilePath $PythonExe -Arguments @("-m", "pip", "install", "--index-url", $TorchIndexUrl, "torch==$TorchVersion") -LogName "torch-install.log" -FailureMessage "CUDA-enabled PyTorch installation failed. CPU-only PyTorch is not allowed."
    }
    Verify-Cuda
    $torchJson = (& $PythonExe -c "import json,torch; print(json.dumps({'version':torch.__version__,'cuda':torch.version.cuda,'devices':[torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]}))") | ConvertFrom-Json
    Complete-InstallStage "cuda-torch" -Action $action -Details @{ version=$torchJson.version; cuda=$torchJson.cuda; devices=@($torchJson.devices); index=$TorchIndexUrl }
}

function Ensure-BackendDependencies {
    Write-Step "Checking backend dependencies"
    $requirements = Join-Path $BackendRoot "requirements.txt"
    $pyproject = Join-Path $BackendRoot "pyproject.toml"
    $fingerprint = Get-FilesFingerprint -Paths @($requirements, $pyproject) -AdditionalValues @($TorchVersion, (& $PythonExe -c "import sys; print(sys.version)"))
    $record = Get-StageRecord "backend-dependencies"
    $pipCheck = Invoke-Capture -FilePath $PythonExe -Arguments @("-m", "pip", "check")
    $dryRun = Invoke-Capture -FilePath $PythonExe -Arguments @("-m", "pip", "install", "--dry-run", "--no-deps", "-r", $requirements)
    $imports = Invoke-Capture -FilePath $PythonExe -Arguments @("-c", "import cial_knowledge_os,fastapi,sqlalchemy,qdrant_client,sentence_transformers") -WorkingDirectory $BackendRoot
    $healthy = $record.fingerprint -eq $fingerprint -and $pipCheck.ExitCode -eq 0 -and $dryRun.ExitCode -eq 0 -and $dryRun.Output -notmatch "(?m)^Would install " -and $imports.ExitCode -eq 0
    $action = "skipped"
    if (-not $healthy) {
        $action = if ($null -eq $record) { "installed" } else { "repaired" }
        Invoke-ComponentCommand -FilePath $PythonExe -Arguments @("-m", "pip", "install", "-r", $requirements) -LogName "backend-dependencies.log" -FailureMessage "Backend dependency installation failed."
        Invoke-ComponentCommand -FilePath $PythonExe -Arguments @("-m", "pip", "install", "-e", $BackendRoot) -LogName "backend-editable-install.log" -FailureMessage "Editable backend package installation failed."
    }
    if (-not (Test-CudaTorch)) { Stop-Install "Backend dependency resolution replaced or invalidated CUDA PyTorch." }
    $pipCheck = Invoke-Capture -FilePath $PythonExe -Arguments @("-m", "pip", "check")
    if ($pipCheck.ExitCode -ne 0) { Stop-Install "Backend environment dependency validation failed: $($pipCheck.Output)" }
    Complete-InstallStage "backend-dependencies" -Action $action -Details @{ fingerprint=$fingerprint; requirements=$requirements; requirements_hash=(Get-FileHash $requirements -Algorithm SHA256).Hash; pyproject_hash=(Get-FileHash $pyproject -Algorithm SHA256).Hash; pip_check="ok" }
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
for index in range(torch.cuda.device_count()):
    print(f"gpu[{index}]=" + torch.cuda.get_device_name(index))
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
    Write-Step "Downloading/verifying embedding and reranker model caches"
    $env:TRANSFORMERS_OFFLINE = "0"
    $env:HF_HUB_OFFLINE = "0"
    $env:CIAL_MODEL_REPORT_PATH = Join-Path $StateRoot "model-cache.json"
    $script = @"
from sentence_transformers import SentenceTransformer, CrossEncoder
from huggingface_hub import snapshot_download
import json
import os
def stage(repo_id, loader):
    try:
        path = snapshot_download(repo_id=repo_id, local_files_only=True)
        return path, loader(path), "cached"
    except Exception:
        path = snapshot_download(repo_id=repo_id)
        try:
            return path, loader(path), "installed"
        except Exception:
            path = snapshot_download(repo_id=repo_id, force_download=True)
            return path, loader(path), "repaired"
embedding_path, embedding_model, embedding_action = stage("$EmbeddingModel", lambda path: SentenceTransformer(path, device="cuda", local_files_only=True))
reranker_path, reranker, reranker_action = stage("$RerankerModel", lambda path: CrossEncoder(path, device="cuda", local_files_only=True))
embedding = embedding_model.encode(["CIAL CUDA embedding smoke test"], convert_to_tensor=True)
print("embedding_device=" + str(embedding.device))
score = reranker.predict([("query", "document")])
print("reranker_score=" + str(score[0]))
print("hf_home=" + os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface")))
with open(os.environ["CIAL_MODEL_REPORT_PATH"], "w", encoding="utf-8") as handle:
    json.dump({"embedding_snapshot": embedding_path, "reranker_snapshot": reranker_path, "embedding_action": embedding_action, "reranker_action": reranker_action}, handle, indent=2)
"@
    $modelOutput = $script | & $PythonExe - 2>&1
    $modelExit = $LASTEXITCODE
    $modelOutput | Set-Content -LiteralPath (Join-Path $ComponentLogsRoot "huggingface-models.log") -Encoding UTF8
    $modelOutput | ForEach-Object { Write-Host "$_" }
    if ($modelExit -ne 0) {
        Stop-Install "Embedding or reranker model download/CUDA verification failed."
    }
    $env:TRANSFORMERS_OFFLINE = "1"
    $env:HF_HUB_OFFLINE = "1"
    Set-EnvFileValue -Path $BackendEnvPath -Values @{ "CIAL_LOCAL_FILES_ONLY" = "true"; "TRANSFORMERS_OFFLINE" = "1"; "HF_HUB_OFFLINE" = "1" }
    $cache = Get-Content -LiteralPath (Join-Path $StateRoot "model-cache.json") -Raw | ConvertFrom-Json
    $modelAction = if ($cache.embedding_action -eq "cached" -and $cache.reranker_action -eq "cached") { "skipped" } elseif ($cache.embedding_action -eq "repaired" -or $cache.reranker_action -eq "repaired") { "repaired" } else { "installed" }
    Complete-InstallStage "huggingface-models" -Action $modelAction -Details @{ embedding_snapshot=$cache.embedding_snapshot; reranker_snapshot=$cache.reranker_snapshot; offline=$true }
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
    Set-EnvFileValue -Path $BackendEnvPath -Values @{ "TESSERACT_CMD" = $tesseract; "CIAL_LIBREOFFICE_PATH" = $soffice }
    $env:TESSERACT_CMD = $tesseract
    $ocr = & $PythonExe -c "import os,pytesseract; pytesseract.pytesseract.tesseract_cmd=os.environ['TESSERACT_CMD']; print(pytesseract.get_tesseract_version())" 2>&1
    if ($LASTEXITCODE -ne 0) { Stop-Install "Tesseract Python smoke test failed: $ocr" }
    $officeSmoke = Join-Path $StateRoot "office-smoke"
    New-Item -ItemType Directory -Force -Path $officeSmoke | Out-Null
    $source = Join-Path $officeSmoke "render-smoke.txt"
    Set-Content -LiteralPath $source -Value "CIAL Knowledge OS document rendering smoke test" -Encoding UTF8
    & $soffice --headless --convert-to pdf --outdir $officeSmoke $source | Out-Null
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath (Join-Path $officeSmoke "render-smoke.pdf") -PathType Leaf)) {
        Stop-Install "LibreOffice headless document rendering smoke test failed."
    }
    @("tesseract=$tesseract", "ocr=$ocr", "libreoffice=$soffice", "office_pdf=$(Join-Path $officeSmoke 'render-smoke.pdf')") | Set-Content -LiteralPath (Join-Path $ComponentLogsRoot "ocr-document-rendering.log") -Encoding UTF8
    Complete-InstallStage "ocr-document-rendering" -Action "verified" -Details @{ tesseract=$tesseract; libreoffice=$soffice; office_smoke="ok"; ocr_smoke="ok" }
}

function Ensure-NodeFrontend {
    Write-Step "Installing and building frontend"
    Stop-ExistingCialFrontendForInstall
    $toolchain = Resolve-NodeFrontendToolchain
    $hadExistingNodeModules = Test-Path -LiteralPath (Join-Path $FrontendRoot "node_modules") -PathType Container
    $fingerprint = Get-FilesFingerprint -Paths @((Join-Path $FrontendRoot "package.json"), (Join-Path $FrontendRoot "pnpm-lock.yaml")) -AdditionalValues @($toolchain.PnpmVersion)
    $record = Get-StageRecord "frontend-dependencies"
    $vite = Join-Path $FrontendRoot "node_modules\.bin\vite.cmd"
    $tsc = Join-Path $FrontendRoot "node_modules\.bin\tsc.cmd"
    $dependenciesHealthy = $record.fingerprint -eq $fingerprint -and $hadExistingNodeModules -and (Test-Path -LiteralPath $vite -PathType Leaf) -and (Test-Path -LiteralPath $tsc -PathType Leaf)
    $action = "skipped"
    if (-not $dependenciesHealthy) {
        $action = if ($null -eq $record -and -not $hadExistingNodeModules) { "installed" } else { "repaired" }
        Invoke-Logged -FilePath $toolchain.Pnpm -Arguments @("install", "--frozen-lockfile") -WorkingDirectory $FrontendRoot -FailureMessage "Frontend pnpm install failed."
    } else { Write-Host "Frontend dependency fingerprint is current; skipping pnpm install." }

    if ($VerifyCleanFrontendInstall -or (-not $dependenciesHealthy -and $hadExistingNodeModules)) {
        Invoke-CleanFrontendInstallVerification -Pnpm $toolchain.Pnpm
    }

    if (-not (Test-Path -LiteralPath $vite -PathType Leaf)) {
        Stop-Install "Local Vite executable was not found after dependency installation: $vite"
    }
    if (-not (Test-Path -LiteralPath $tsc -PathType Leaf)) {
        Stop-Install "Local TypeScript executable was not found after dependency installation: $tsc"
    }
    $env:PORT = "$FrontendPort"
    $env:VITE_API_BASE_URL = "http://127.0.0.1:$BackendPort"
    Invoke-ComponentCommand -FilePath $vite -Arguments @("build") -LogName "frontend-build.log" -WorkingDirectory $FrontendRoot -FailureMessage "Frontend production build failed."
    Invoke-ComponentCommand -FilePath $tsc -Arguments @("-p", "tsconfig.json", "--noEmit") -LogName "frontend-typecheck.log" -WorkingDirectory $FrontendRoot -FailureMessage "Frontend typecheck failed."
    Complete-InstallStage "frontend-dependencies" -Action $action -Details @{ fingerprint=$fingerprint; package_hash=(Get-FileHash (Join-Path $FrontendRoot "package.json") -Algorithm SHA256).Hash; lockfile_hash=(Get-FileHash (Join-Path $FrontendRoot "pnpm-lock.yaml") -Algorithm SHA256).Hash; pnpm=$toolchain.Pnpm; pnpm_version=$toolchain.PnpmVersion; node=$toolchain.Node; npm=$toolchain.Npm; corepack=$toolchain.Corepack }
    Complete-InstallStage "frontend-build" -Action "verified" -Details @{ output=(Join-Path $FrontendRoot "dist\public\index.html"); fingerprint=$fingerprint }
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
    $hadConfig = Test-Path -LiteralPath $AppConfigPath -PathType Leaf
    $existingValid = $false
    if (Test-Path -LiteralPath $AppConfigPath -PathType Leaf) {
        try {
            $config = Get-Content -LiteralPath $AppConfigPath -Raw | ConvertFrom-Json
            $repo = @($config.repositories | Where-Object { $_.id -eq "enterprise" -and $_.enabled -ne $false } | Select-Object -First 1)
            if ($repo.Count -gt 0 -and (Test-Path -LiteralPath $repo[0].path -PathType Container)) {
                $probe = Join-Path $repo[0].path (".cial-installer-probe-{0}.tmp" -f [guid]::NewGuid().ToString("N"))
                try {
                    Get-ChildItem -LiteralPath $repo[0].path -Force -ErrorAction Stop | Select-Object -First 1 | Out-Null
                    [IO.File]::WriteAllText($probe, "CIAL repository validation")
                    Remove-Item -LiteralPath $probe -Force
                    $existingValid = $true
                    Write-Host "Existing enterprise repository config is valid and will be preserved: $($repo[0].path)"
                } catch {
                    if (Test-Path -LiteralPath $probe) { Remove-Item -LiteralPath $probe -Force -ErrorAction SilentlyContinue }
                    Write-Host "Existing enterprise repository is not readable/writable; repository selection is required." -ForegroundColor Yellow
                }
            }
        }
        catch {
            Write-Host "Existing application config could not be parsed; first-run corpus selection is required."
        }
    }
    if ($existingValid) {
        Complete-InstallStage "repository" -Action "skipped" -Details @{ path=$repo[0].path; repository_id=$repo[0].repository_id; config=$AppConfigPath }
        return
    }
    $configScript = Join-Path $RepoRoot "scripts\configure_corpus_repository.ps1"
    if (-not (Test-Path -LiteralPath $configScript -PathType Leaf)) {
        Stop-Install "Missing corpus configuration helper: $configScript"
    }
    if ([string]::IsNullOrWhiteSpace($CorpusRepositoryPath)) {
        Add-Type -AssemblyName System.Windows.Forms
        $picker = New-Object System.Windows.Forms.FolderBrowserDialog
        $picker.Description = "Select the CIAL Enterprise Knowledge Repository"
        $picker.ShowNewFolderButton = $true
        if ($picker.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) {
            Stop-Install "Enterprise repository selection was cancelled. Rerun the installer to resume."
        }
        $CorpusRepositoryPath = $picker.SelectedPath
    }
    $arguments = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $configScript, "-ConfigPath", $AppConfigPath, "-RepositoryPath", $CorpusRepositoryPath)
    Invoke-Logged -FilePath "powershell.exe" -Arguments $arguments -WorkingDirectory $RepoRoot -FailureMessage "Enterprise repository configuration failed or was cancelled."
    $saved = Get-Content -LiteralPath $AppConfigPath -Raw | ConvertFrom-Json
    $savedRepo = @($saved.repositories | Where-Object { $_.id -eq "enterprise" } | Select-Object -First 1)[0]
    Complete-InstallStage "repository" -Action $(if($hadConfig){"repaired"}else{"installed"}) -Details @{ path=$savedRepo.path; repository_id=$savedRepo.repository_id; config=$AppConfigPath }
}

function Run-Alembic {
    Write-Step "Running Alembic migrations"
    Push-Location $BackendRoot
    try {
        $heads = (& $PythonExe -m alembic heads) -join "`n"
        if ($LASTEXITCODE -ne 0) { Stop-Install "alembic heads failed." }
        $headRevision = ([regex]::Match($heads, "(?m)^([0-9A-Za-z_]+)\s+\(head\)")).Groups[1].Value
        if ([string]::IsNullOrWhiteSpace($headRevision)) { Stop-Install "Could not determine the repository Alembic head." }
        $current = (& $PythonExe -m alembic current) -join "`n"
        if ($LASTEXITCODE -ne 0) { Stop-Install "alembic current failed." }
        $action = "skipped"
        if ($current -notmatch [regex]::Escape($headRevision)) {
            $upgrade = (& $PythonExe -m alembic upgrade head 2>&1) -join "`n"
            $upgradeExitCode = $LASTEXITCODE
            Write-Host $upgrade
            if ($upgradeExitCode -ne 0) { Stop-Install "alembic upgrade head failed. No downgrade or data reset was attempted." }
            $action = "repaired"
            $current = (& $PythonExe -m alembic current) -join "`n"
        } else { Write-Host "Database is already at Alembic head; skipping migration upgrade." }
        Write-Host $current
        Write-Host $heads
        if ($current -notmatch [regex]::Escape($headRevision)) {
            Stop-Install "Alembic current revision is not at repository head after upgrade."
        }
        @("HEADS:", $heads, "CURRENT:", $current, "ACTION: $action") | Set-Content -LiteralPath (Join-Path $ComponentLogsRoot "alembic.log") -Encoding UTF8
        Complete-InstallStage "migrations" -Action $action -Details @{ current=$headRevision; head=$headRevision }
        return $headRevision
    }
    finally {
        Pop-Location
    }
}

function Start-Application {
    Write-Step "Starting application through daily launcher"
    $launcher = Join-Path $RepoRoot "Launch-CIAL-Knowledge-OS.ps1"
    Invoke-Logged -FilePath "powershell.exe" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $launcher, "-BackendPort", "$BackendPort", "-FrontendPort", "$FrontendPort", "-QdrantUrl", $QdrantUrl, "-PostgresContainerName", $PostgresContainerName, "-OllamaModel", $OllamaModel, "-EmbeddingModel", $EmbeddingModel, "-RerankerModel", $RerankerModel, "-NoBrowser:$($NoBrowser.IsPresent)") -WorkingDirectory $RepoRoot -FailureMessage "Daily launcher failed during installer verification."
}

function Invoke-AcceptanceAndWriteFinalReport {
    Write-Step "Running post-install acceptance tests"
    $verificationScript = Join-Path $RepoRoot "scripts\verify_windows_installation.ps1"
    Invoke-Logged -FilePath "powershell.exe" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $verificationScript, "-BackendPort", "$BackendPort", "-FrontendPort", "$FrontendPort", "-QdrantUrl", $QdrantUrl, "-ReportDirectory", $ReportRoot) -FailureMessage "Mandatory post-install acceptance tests failed. Installation is not certified; review the acceptance report."
    $acceptancePath = (Get-ChildItem -LiteralPath $ReportRoot -Filter "acceptance-*.json" | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
    $acceptance = Get-Content -LiteralPath $acceptancePath -Raw | ConvertFrom-Json
    $acceptanceTextPath = [IO.Path]::ChangeExtension($acceptancePath, ".txt")
    if (Test-Path -LiteralPath $acceptanceTextPath) { Copy-Item -LiteralPath $acceptanceTextPath -Destination (Join-Path $ComponentLogsRoot "acceptance.log") -Force }
    Complete-InstallStage "acceptance" -Action "verified" -Details @{ report=$acceptancePath; success=$true }

    $gpu = Get-CimInstance Win32_VideoController | Where-Object { $_.Name -match "NVIDIA" } | Select-Object -First 1
    $torch = (& $PythonExe -c "import json,torch; print(json.dumps({'version':torch.__version__,'cuda':torch.version.cuda,'available':torch.cuda.is_available(),'devices':[torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]}))") | ConvertFrom-Json
    $app = Get-Content -LiteralPath $AppConfigPath -Raw | ConvertFrom-Json
    $repo = @($app.repositories | Where-Object { $_.id -eq "enterprise" -and $_.enabled -ne $false } | Select-Object -First 1)[0]
    $backendEnv = Get-EnvMap -Paths @($BackendEnvPath)
    $tesseractPath = $backendEnv["TESSERACT_CMD"]
    $libreOfficePath = $backendEnv["CIAL_LIBREOFFICE_PATH"]
    $paths = [ordered]@{ python=$PythonExe; git=(Get-CommandPath "git.exe"); node=(Get-CommandPath "node.exe"); docker=(Get-CommandPath "docker.exe"); ollama=(Get-CommandPath "ollama.exe"); tesseract=$tesseractPath; libreoffice=$libreOfficePath }
    $versions = [ordered]@{}
    foreach ($entry in $paths.GetEnumerator()) {
        if (-not [string]::IsNullOrWhiteSpace($entry.Value)) {
            $check = Test-ExecutableVersion -Label $entry.Key -FilePath $entry.Value
            $versions[$entry.Key] = if ($check.Ok) { $check.Version } else { $check.Error }
        }
    }
    $hfCache = [Environment]::GetEnvironmentVariable("HF_HOME")
    if ([string]::IsNullOrWhiteSpace($hfCache)) { $hfCache = Join-Path $env:USERPROFILE ".cache\huggingface" }
    $modelSnapshots = $null
    $modelCacheReport = Join-Path $StateRoot "model-cache.json"
    if (Test-Path -LiteralPath $modelCacheReport -PathType Leaf) { $modelSnapshots = Get-Content -LiteralPath $modelCacheReport -Raw | ConvertFrom-Json }
    $installationState = Get-InstallState
    $report = [ordered]@{
        generated_at=(Get-Date).ToUniversalTime().ToString("o"); success=$true
        detected_state=$installationState
        repository=[ordered]@{ path=$repo.path; repository_id=$repo.repository_id }
        urls=[ordered]@{ backend="http://127.0.0.1:$BackendPort"; frontend="http://127.0.0.1:$FrontendPort/login"; qdrant=$QdrantUrl; ollama="http://127.0.0.1:11434" }
        gpu=[ordered]@{ name=$gpu.Name; driver=$gpu.DriverVersion }
        torch=$torch
        models=[ordered]@{ ollama=$OllamaModel; embedding=$EmbeddingModel; reranker=$RerankerModel; huggingface_cache=$hfCache; snapshots=$modelSnapshots }
        executables=$paths
        prerequisite_versions=$versions
        database=[ordered]@{ verified=$true; credentials_redacted=$true; alembic_head=$alembicHead }
        acceptance_report=$acceptancePath
        acceptance_results=$acceptance.results
        warnings=@($acceptance.warnings)
        manual_actions=@($acceptance.warnings)
        logs=[ordered]@{ installer=$LogPath; components=$ComponentLogsRoot; reports=$ReportRoot }
    }
    $finalJson = Join-Path $ReportRoot "installation-final-$Timestamp.json"
    $finalText = Join-Path $ReportRoot "installation-final-$Timestamp.txt"
    $report | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $finalJson -Encoding UTF8
    @(
        "CIAL Knowledge OS Installation Successful", "", "CUDA: verified", "PostgreSQL: verified", "Qdrant: verified",
        "Ollama and LLM model: verified", "Embeddings and reranker: verified", "OCR and document rendering: verified",
        "Database migrations: $alembicHead", "Backend and frontend: verified", "Authentication: verified",
        "Repository, retrieval, and citations: verified", "", "System Ready", "JSON report: $finalJson", "Installer log: $LogPath"
    ) | Set-Content -LiteralPath $finalText -Encoding UTF8
    Write-Host "Final reports: $finalJson and $finalText"
}

try {
    Invoke-Preflight

    Write-Step "Installing/verifying prerequisites"
    Ensure-WingetPackage -Id "Git.Git" -DisplayName "Git"
    Ensure-WingetPackage -Id "Python.Python.3.11" -DisplayName "Python 3.11"
    Ensure-WingetPackage -Id "OpenJS.NodeJS.LTS" -DisplayName "Node.js LTS"
    Ensure-WingetPackage -Id "Docker.DockerDesktop" -DisplayName "Docker Desktop"
    Ensure-WingetPackage -Id "Ollama.Ollama" -DisplayName "Ollama"
    Ensure-WingetPackage -Id "UB-Mannheim.TesseractOCR" -DisplayName "Tesseract OCR"
    Ensure-WingetPackage -Id "TheDocumentFoundation.LibreOffice" -DisplayName "LibreOffice"
    Ensure-WingetPackage -Id "Microsoft.VCRedist.2015+.x64" -DisplayName "Microsoft Visual C++ Runtime"
    Refresh-ProcessPath
    Verify-PrerequisiteExecutables
    Complete-InstallStage "prerequisites"

    Ensure-BackendEnv
    Ensure-FrontendEnv
    Complete-InstallStage "configuration"
    Ensure-DockerDesktop
    Ensure-Postgres
    Ensure-Qdrant
    Ensure-Ollama
    Ensure-PythonEnvironment
    Ensure-CudaTorch
    Ensure-BackendDependencies
    Verify-PostgresConnection
    Verify-ModelCaches
    Complete-InstallStage "models"
    Verify-OcrAndOffice
    Ensure-NodeFrontend
    Ensure-CorpusConfiguration
    $alembicHead = Run-Alembic
    Start-Application
    Complete-InstallStage "startup" -Action "verified" -Details @{ backend="http://127.0.0.1:$BackendPort"; frontend="http://127.0.0.1:$FrontendPort/login" }
    Invoke-AcceptanceAndWriteFinalReport

    Write-Host ""
    Write-Host "CIAL Knowledge OS Installation Successful" -ForegroundColor Green
    Write-Host "System Ready" -ForegroundColor Green
    Write-Host "Install log: $LogPath"
}
catch {
    $state = Get-InstallState
    $safeFailure = $_.Exception.Message -replace '(?i)postgresql\+psycopg://[^\s@]+@','postgresql+psycopg://<redacted>@'
    $state | Add-Member -NotePropertyName "last_failure" -NotePropertyValue $safeFailure -Force
    $state | Add-Member -NotePropertyName "last_failure_at" -NotePropertyValue (Get-Date).ToUniversalTime().ToString("o") -Force
    Save-InstallState $state
    [ordered]@{ generated_at=(Get-Date).ToUniversalTime().ToString("o"); success=$false; failure=$safeFailure; state=$state; installer_log=$LogPath; component_logs=$ComponentLogsRoot } | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $ReportRoot "installation-failure-$Timestamp.json") -Encoding UTF8
    throw
}
finally {
    Stop-Transcript | Out-Null
}
