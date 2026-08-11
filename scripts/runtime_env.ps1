Set-StrictMode -Version Latest

function Read-CialEnvFile {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$Path
    )

    $values = @{}
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $values
    }

    $lineNumber = 0
    foreach ($rawLine in [System.IO.File]::ReadAllLines($Path)) {
        $lineNumber++
        $line = $rawLine.Trim()
        if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith("#")) {
            continue
        }
        if ($line.StartsWith("export ", [StringComparison]::Ordinal)) {
            $line = $line.Substring(7).TrimStart()
        }
        if (-not $line.Contains("=")) {
            throw "Invalid environment assignment in '$Path' at line $lineNumber. Expected KEY=VALUE."
        }
        $parts = $line.Split("=", 2)
        $key = $parts[0].Trim()
        if ($key -notmatch "^[A-Za-z_][A-Za-z0-9_]*$") {
            throw "Invalid environment key in '$Path' at line $lineNumber."
        }
        $value = $parts[1].Trim()
        if ($value.Length -ge 2 -and (
            ($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))
        )) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        $values[$key] = $value
    }
    return $values
}

function Get-CialRuntimeEnvPaths {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$RepoRoot
    )

    $resolvedRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
    $paths = [System.Collections.Generic.List[string]]::new()
    foreach ($candidate in @(
        (Join-Path $resolvedRoot ".env"),
        (Join-Path $resolvedRoot "services\knowledge-engine\.env"),
        (Join-Path $resolvedRoot "services\knowledge-engine\backend\.env")
    )) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            $paths.Add((Resolve-Path -LiteralPath $candidate).Path)
        }
    }

    $customPath = [Environment]::GetEnvironmentVariable("CIAL_RUNTIME_ENV_FILE", "Process")
    if (-not [string]::IsNullOrWhiteSpace($customPath)) {
        $customCandidate = if ([IO.Path]::IsPathRooted($customPath)) {
            $customPath
        }
        else {
            Join-Path $resolvedRoot $customPath
        }
        if (-not (Test-Path -LiteralPath $customCandidate -PathType Leaf)) {
            throw "CIAL_RUNTIME_ENV_FILE does not identify a readable file."
        }
        $customResolved = (Resolve-Path -LiteralPath $customCandidate).Path
        if (-not $paths.Contains($customResolved)) {
            $paths.Add($customResolved)
        }
    }
    return @($paths)
}

function Get-CialEnvironmentMap {
    [CmdletBinding()]
    param(
        [string[]]$Paths = @(),
        [switch]$IncludeProcessEnvironment
    )

    $map = @{}
    foreach ($path in $Paths) {
        if ([string]::IsNullOrWhiteSpace($path)) { continue }
        $fileValues = Read-CialEnvFile -Path $path
        foreach ($key in $fileValues.Keys) {
            $map[$key] = $fileValues[$key]
        }
    }
    if ($IncludeProcessEnvironment) {
        foreach ($entry in [Environment]::GetEnvironmentVariables("Process").GetEnumerator()) {
            $map[[string]$entry.Key] = [string]$entry.Value
        }
    }
    return $map
}

function Import-CialRuntimeEnvironment {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$RepoRoot,
        [string[]]$RequiredKeys = @(),
        [switch]$Quiet
    )

    $paths = @(Get-CialRuntimeEnvPaths -RepoRoot $RepoRoot)
    $processEnvironment = [Environment]::GetEnvironmentVariables("Process")
    $fileValues = Get-CialEnvironmentMap -Paths $paths
    $loadedKeys = [System.Collections.Generic.List[string]]::new()
    foreach ($key in $fileValues.Keys) {
        if (-not $processEnvironment.Contains($key)) {
            [Environment]::SetEnvironmentVariable($key, [string]$fileValues[$key], "Process")
            $loadedKeys.Add($key)
        }
    }

    if (-not $Quiet) {
        if ($paths.Count -eq 0) {
            Write-Host "Server configuration source: process environment only."
        }
        else {
            foreach ($path in $paths) {
                Write-Host "Server configuration source loaded: $path"
            }
            Write-Host "Explicit process environment values take precedence."
        }
    }

    $missing = @(
        $RequiredKeys | Where-Object {
            [string]::IsNullOrWhiteSpace(
                [Environment]::GetEnvironmentVariable($_, "Process")
            )
        }
    )
    if ($missing.Count -gt 0) {
        throw "Required server configuration is missing: $($missing -join ', '). No values were printed."
    }

    return [pscustomobject]@{
        Sources = $paths
        LoadedKeyCount = $loadedKeys.Count
        ProcessOverrideCount = $processEnvironment.Count
    }
}

function Get-CialScopedEnvironmentValue {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$Name,
        [Parameter(Mandatory)]
        [string]$ProtectedPath
    )

    $processEnvironment = [Environment]::GetEnvironmentVariables("Process")
    if ($processEnvironment.Contains($Name)) {
        $value = [string]$processEnvironment[$Name]
        if ([string]::IsNullOrWhiteSpace($value)) {
            throw "$Name was explicitly supplied but is empty."
        }
        Write-Host "Scoped configuration source for ${Name}: process environment."
        return $value
    }
    $map = Read-CialEnvFile -Path $ProtectedPath
    if (-not $map.ContainsKey($Name) -or [string]::IsNullOrWhiteSpace($map[$Name])) {
        throw "Protected scoped configuration is missing: $Name. No value was printed."
    }
    Write-Host "Scoped configuration source for ${Name}: $ProtectedPath"
    return $map[$Name]
}

function Clear-CialMigrationCredential {
    [CmdletBinding()]
    param()

    # Alembic is the only runtime consumer of this privileged credential.
    # Clear it before spawning ordinary application processes so they cannot
    # inherit it from an operator's shell or an installer migration step.
    [Environment]::SetEnvironmentVariable(
        "CIAL_MIGRATION_DATABASE_URL",
        $null,
        "Process"
    )
}
