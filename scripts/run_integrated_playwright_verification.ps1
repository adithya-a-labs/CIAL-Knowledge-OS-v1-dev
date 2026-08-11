$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $repo "frontend"
$backend = Join-Path $repo "services\knowledge-engine"
$python = Join-Path $repo ".venv\Scripts\python.exe"
$outputDir = Join-Path $repo "outputs\playwright"
. (Join-Path $PSScriptRoot "runtime_env.ps1")
Import-CialRuntimeEnvironment -RepoRoot $repo -RequiredKeys @(
    "DATABASE_URL",
    "CIAL_QDRANT_API_KEY"
) | Out-Null
Clear-CialMigrationCredential
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

function Stop-PortListener {
    param([int]$Port)

    $lines = netstat -ano | Select-String ":$Port\s"
    foreach ($line in $lines) {
        $parts = ($line.Line -split "\s+") | Where-Object { $_ }
        if ($parts.Length -lt 5 -or $parts[1] -notmatch ":$Port$") {
            continue
        }

        $processId = [int]$parts[-1]
        if ($processId -gt 0) {
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        }
    }
}

function Wait-Url {
    param(
        [string]$Url,
        [int]$Seconds = 90
    )

    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 5
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return $true
            }
        }
        catch {
            Start-Sleep -Seconds 2
        }
    } while ((Get-Date) -lt $deadline)

    return $false
}

function Wait-EngineReady {
    param([int]$Seconds = 180)

    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 5
            $body = $response.Content | ConvertFrom-Json
            if ($body.engine_ready -eq $true) {
                return $true
            }
        }
        catch {
            Start-Sleep -Seconds 2
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)

    return $false
}

Stop-PortListener -Port 5173
Stop-PortListener -Port 8000

$backendJob = Start-Job -Name "cial-backend-verification" -ScriptBlock {
    param($BackendPath, $PythonPath)
    Set-Location $BackendPath
    & $PythonPath -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
} -ArgumentList $backend, $python

$frontendJob = Start-Job -Name "cial-frontend-verification" -ScriptBlock {
    param($FrontendPath)
    $env:PORT = "5173"
    $env:VITE_API_BASE_URL = "http://127.0.0.1:8000"
    Set-Location $FrontendPath
    & pnpm.cmd run dev
} -ArgumentList $frontend

try {
    $backendReady = Wait-Url -Url "http://127.0.0.1:8000/api/health" -Seconds 120
    $frontendReady = Wait-Url -Url "http://127.0.0.1:5173" -Seconds 60
    $engineReady = Wait-EngineReady -Seconds 180

    "backend_ready=$backendReady" | Tee-Object -FilePath (Join-Path $outputDir "integrated-launch-status.txt")
    "frontend_ready=$frontendReady" | Tee-Object -FilePath (Join-Path $outputDir "integrated-launch-status.txt") -Append
    "engine_ready=$engineReady" | Tee-Object -FilePath (Join-Path $outputDir "integrated-launch-status.txt") -Append

    Set-Location $frontend
    & pnpm.cmd exec node ..\scripts\verify_integrated_frontend.mjs
}
finally {
    Receive-Job -Job $backendJob -Keep -ErrorAction SilentlyContinue 6>&1 | Out-File -FilePath (Join-Path $outputDir "backend-job.log") -Encoding utf8
    Receive-Job -Job $frontendJob -Keep -ErrorAction SilentlyContinue 6>&1 | Out-File -FilePath (Join-Path $outputDir "frontend-job.log") -Encoding utf8
    Stop-Job -Job $backendJob, $frontendJob -ErrorAction SilentlyContinue
    Remove-Job -Job $backendJob, $frontendJob -Force -ErrorAction SilentlyContinue
}
