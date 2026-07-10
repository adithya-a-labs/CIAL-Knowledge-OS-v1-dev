param(
    [string]$RepositoryPath = "",
    [string]$ConfigPath = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
    $ConfigPath = Join-Path $RepoRoot "data\config\application.json"
}

if ([string]::IsNullOrWhiteSpace($RepositoryPath)) {
    $RepositoryPath = Read-Host "Enterprise Knowledge Repository folder"
}

if ([string]::IsNullOrWhiteSpace($RepositoryPath)) {
    throw "Repository folder is required."
}

$resolvedRepository = (Resolve-Path -LiteralPath $RepositoryPath).Path
if (-not (Test-Path -LiteralPath $resolvedRepository -PathType Container)) {
    throw "Configured corpus directory does not exist: $resolvedRepository"
}

try {
    Get-ChildItem -LiteralPath $resolvedRepository -Force -ErrorAction Stop | Select-Object -First 1 | Out-Null
} catch {
    throw "Configured corpus directory is not readable by this account: $resolvedRepository"
}

$configDirectory = Split-Path -Parent $ConfigPath
New-Item -ItemType Directory -Path $configDirectory -Force | Out-Null

if (Test-Path -LiteralPath $ConfigPath -PathType Leaf) {
    $config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
} else {
    $config = [pscustomobject]@{}
}

$existingRepositories = @()
if ($null -ne $config.repositories) {
    $existingRepositories = @($config.repositories | Where-Object { $_.id -ne "enterprise" })
}

$normalizedRepository = $resolvedRepository.ToLowerInvariant()
$sha = [System.Security.Cryptography.SHA256]::Create()
try {
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($normalizedRepository)
    $hashBytes = $sha.ComputeHash($bytes)
    $repositoryId = "repo-" + (($hashBytes | ForEach-Object { $_.ToString("x2") }) -join "").Substring(0, 16)
}
finally {
    $sha.Dispose()
}

$primaryRepository = [ordered]@{
    id = "enterprise"
    repository_id = $repositoryId
    name = "Enterprise Knowledge Repository"
    type = "filesystem"
    path = $resolvedRepository
    enabled = $true
    role = "primary"
}

$config | Add-Member -NotePropertyName "version" -NotePropertyValue 1 -Force
$config | Add-Member -NotePropertyName "repositories" -NotePropertyValue @($primaryRepository) -Force
if ($existingRepositories.Count -gt 0) {
    $config.repositories = @($primaryRepository) + $existingRepositories
}

$config | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ConfigPath -Encoding UTF8

Write-Host "Saved enterprise repository configuration:" -ForegroundColor Green
Write-Host "  Repository: $resolvedRepository"
Write-Host "  Repository ID: $repositoryId"
Write-Host "  Config:     $ConfigPath"
