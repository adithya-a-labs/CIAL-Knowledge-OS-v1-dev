param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [string]$QdrantUrl = "http://127.0.0.1:6335",
    [string]$ReportDirectory = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
. (Join-Path $PSScriptRoot "runtime_env.ps1")
Import-CialRuntimeEnvironment -RepoRoot $RepoRoot -RequiredKeys @(
    "DATABASE_URL",
    "CIAL_AUTH_SECRET_KEY",
    "CIAL_QDRANT_API_KEY"
) | Out-Null
if ([string]::IsNullOrWhiteSpace($ReportDirectory)) { $ReportDirectory = Join-Path $RepoRoot "outputs\installer\reports" }
New-Item -ItemType Directory -Force -Path $ReportDirectory | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$jsonPath = Join-Path $ReportDirectory "acceptance-$timestamp.json"
$textPath = Join-Path $ReportDirectory "acceptance-$timestamp.txt"
$base = "http://127.0.0.1:$BackendPort"
$results = [ordered]@{}
$warnings = New-Object System.Collections.Generic.List[string]
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$temporaryEmail = $null

function Set-Result([string]$Name, [bool]$Passed, [string]$Detail) {
    $script:results[$Name] = [ordered]@{ passed=$Passed; detail=$Detail }
    if (-not $Passed) { Write-Host "[FAIL] $Name - $Detail" -ForegroundColor Red }
    else { Write-Host "[PASS] $Name - $Detail" -ForegroundColor Green }
}

function Invoke-Json([string]$Method, [string]$Uri, [object]$Body=$null, [switch]$AllowFailure) {
    $parameters = @{ Method=$Method; Uri=$Uri; WebSession=$session; UseBasicParsing=$true; TimeoutSec=300 }
    if ($null -ne $Body) { $parameters.ContentType="application/json"; $parameters.Body=($Body | ConvertTo-Json -Depth 8) }
    try { return Invoke-WebRequest @parameters }
    catch { if ($AllowFailure) { return $_.Exception.Response }; throw }
}

try {
    $healthResponse = Invoke-Json GET "$base/api/health"
    $health = $healthResponse.Content | ConvertFrom-Json
    Set-Result "backend" ($health.service -eq "cial-knowledge-os" -and $health.phase -eq "4.5") "service=$($health.service), phase=$($health.phase)"
    Set-Result "postgresql" ($health.database_ready -eq $true) "$($health.database_message)"
    Set-Result "engine" ($health.engine_ready -eq $true -or $health.status -eq "no_documents") "status=$($health.status), message=$($health.message)"

    $loginPage = Invoke-Json GET "http://127.0.0.1:$FrontendPort/login"
    Set-Result "frontend" ($loginPage.StatusCode -eq 200 -and $loginPage.Content -match "CIAL Knowledge OS") "verified CIAL login shell"
    $assetMatch = [regex]::Match($loginPage.Content, '<script[^>]+src="([^"]+)"')
    if ($assetMatch.Success) {
        $asset = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$FrontendPort$($assetMatch.Groups[1].Value)" -TimeoutSec 60
        Set-Result "frontend_backend_configuration" ($asset.StatusCode -eq 200 -and $asset.Content -match [regex]::Escape($base)) "production bundle targets $base"
    } else { Set-Result "frontend_backend_configuration" $false "production JavaScript entry was not found" }

    $email = "installer-verification-$([guid]::NewGuid().ToString('N'))@localhost.invalid"
    $temporaryEmail = $email
    $password = "Cial!$([guid]::NewGuid().ToString('N'))aA1"
    $signup = Invoke-Json POST "$base/api/auth/signup" @{ full_name="Installer Verification"; email=$email; password=$password }
    Set-Result "signup" ($signup.StatusCode -eq 200) "temporary account created"
    $me = Invoke-Json GET "$base/api/auth/me"
    Set-Result "session_persistence" ($me.StatusCode -eq 200 -and $me.Content -match [regex]::Escape($email)) "cookie session persisted"
    $logout = Invoke-Json POST "$base/api/auth/logout" @{}
    Set-Result "logout" ($logout.StatusCode -eq 200) "logout accepted"
    $loggedOutMe = Invoke-Json GET "$base/api/auth/me" -AllowFailure
    Set-Result "protected_route" ([int]$loggedOutMe.StatusCode -eq 401) "logged-out /auth/me returned $([int]$loggedOutMe.StatusCode)"
    $login = Invoke-Json POST "$base/api/auth/login" @{ email=$email; password=$password }
    Set-Result "login" ($login.StatusCode -eq 200) "temporary account login succeeded"
    Invoke-Json POST "$base/api/auth/logout" @{} | Out-Null

    $configPath = Join-Path $RepoRoot "data\config\application.json"
    $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
    $repository = @($config.repositories | Where-Object { $_.id -eq "enterprise" -and $_.enabled -ne $false } | Select-Object -First 1)[0]
    Set-Result "repository" ($null -ne $repository -and (Test-Path -LiteralPath $repository.path -PathType Container)) "repository_id=$($repository.repository_id), path=$($repository.path)"

    $syncResponse = Invoke-Json POST "$base/api/corpus/sync" @{}
    $sync = $syncResponse.Content | ConvertFrom-Json
    Set-Result "corpus_sync" ($syncResponse.StatusCode -eq 200) "corpus synchronization completed"
    $treeResponse = Invoke-Json GET "$base/api/corpus/tree"
    $tree = $treeResponse.Content | ConvertFrom-Json
    $treeJson = $tree | ConvertTo-Json -Depth 50 -Compress
    Set-Result "repository_isolation" ($treeJson -match [regex]::Escape($repository.repository_id)) "active repository ID is present in corpus response"
    Set-Result "qdrant" ($health.qdrant_ready -eq $true) "backend reports Qdrant ready"
    Set-Result "models" ($health.models_ready -eq $true) "backend reports embedding/reranker models ready"
    $qdrantBody = @{ limit=1; with_payload=$true; filter=@{ must=@(@{ key="metadata.repository_id"; match=@{ value=$repository.repository_id } }) } } | ConvertTo-Json -Depth 8
    $qdrantResponse = Invoke-WebRequest -UseBasicParsing -Method Post -Uri "$QdrantUrl/collections/cial_phase4/points/scroll" -Headers @{ "api-key" = $env:CIAL_QDRANT_API_KEY } -ContentType "application/json" -Body $qdrantBody -TimeoutSec 60
    $qdrantPayload = $qdrantResponse.Content | ConvertFrom-Json
    Set-Result "qdrant_repository_data" ($qdrantResponse.StatusCode -eq 200 -and @($qdrantPayload.result.points).Count -gt 0) "active repository vector payload is queryable"

    $chatResponse = Invoke-Json POST "$base/api/chat" @{ question="What is one fact explicitly stated in the active CIAL knowledge repository?"; include_sources=$true; response_length="quick" }
    $chat = $chatResponse.Content | ConvertFrom-Json
    $citations = @($chat.citations)
    $citationRepositoriesOk = $citations.Count -gt 0 -and @($citations | Where-Object { $_.repository_id -ne $repository.repository_id }).Count -eq 0
    Set-Result "retrieval" ($chatResponse.StatusCode -eq 200 -and -not [string]::IsNullOrWhiteSpace($chat.answer)) "grounded chat returned an answer"
    Set-Result "citations" $citationRepositoriesOk "$($citations.Count) citation(s), all scoped to active repository"

    $pdfCitation = @($citations | Where-Object { $_.file_type -eq "pdf" -and $_.document_id -and $_.page } | Select-Object -First 1)
    if ($pdfCitation.Count -gt 0) {
        $pdf = Invoke-WebRequest -UseBasicParsing -Uri "$base/api/corpus/document/$($pdfCitation[0].document_id)/file" -WebSession $session -TimeoutSec 60
        $pdfOk = $pdf.StatusCode -eq 200 -and $pdf.Headers["Content-Type"] -match "application/pdf" -and $pdf.Headers["Content-Disposition"] -match "inline"
        Set-Result "pdf_endpoint" $pdfOk "status=$($pdf.StatusCode), type=$($pdf.Headers['Content-Type']), disposition=$($pdf.Headers['Content-Disposition'])"
        $node = (Get-Command node.exe -ErrorAction SilentlyContinue).Source
        $browserScript = Join-Path $RepoRoot "frontend\scripts\verify-pdf-navigation.mjs"
        if ([string]::IsNullOrWhiteSpace($node)) { Set-Result "pdf_navigation" $false "node.exe was unavailable for browser verification" }
        else {
            & $node $browserScript "$base/api/corpus/document/$($pdfCitation[0].document_id)/file" "$($pdfCitation[0].page)"
            Set-Result "pdf_navigation" ($LASTEXITCODE -eq 0) "Microsoft Edge retained #page=$($pdfCitation[0].page) for the cited native PDF"
        }
    } else {
        $results["pdf_endpoint"] = [ordered]@{ passed=$null; detail="No PDF citation was available; PDF navigation was not certified." }
        $results["pdf_navigation"] = [ordered]@{ passed=$null; detail="No cited PDF with exact page metadata was available." }
        $warnings.Add("No suitable cited PDF with page metadata was available for PDF endpoint/navigation certification.")
    }
} catch {
    Set-Result "acceptance_exception" $false $_.Exception.Message
}

if (-not [string]::IsNullOrWhiteSpace($temporaryEmail)) {
    $python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    $env:CIAL_INSTALLER_TEST_EMAIL = $temporaryEmail
    $previousPythonPath = $env:PYTHONPATH
    $env:PYTHONPATH = "$(Join-Path $RepoRoot 'services\knowledge-engine');$(Join-Path $RepoRoot 'services\knowledge-engine\src')"
    & $python -c "import os; from sqlalchemy import text; from backend.app.db.session import engine; c=engine.connect(); t=c.begin(); c.execute(text('DELETE FROM users WHERE lower(email)=lower(:email)'), {'email':os.environ['CIAL_INSTALLER_TEST_EMAIL']}); t.commit(); c.close()" 2>$null
    $cleanupExit = $LASTEXITCODE
    $env:PYTHONPATH = $previousPythonPath
    Remove-Item Env:CIAL_INSTALLER_TEST_EMAIL -ErrorAction SilentlyContinue
    if ($cleanupExit -eq 0) { Set-Result "temporary_user_cleanup" $true "temporary installer account removed" }
    else { $warnings.Add("Temporary installer verification account cleanup failed; no other data was modified.") }
}

$mandatoryFailures = @($results.GetEnumerator() | Where-Object { $_.Value.passed -eq $false })
$report = [ordered]@{
    generated_at=(Get-Date).ToUniversalTime().ToString("o")
    success=($mandatoryFailures.Count -eq 0)
    backend_url=$base
    frontend_url="http://127.0.0.1:$FrontendPort/login"
    results=$results
    warnings=@($warnings)
}
$report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $jsonPath -Encoding UTF8
$lines = @("CIAL Knowledge OS post-install acceptance", "Success: $($report.success)", "Backend: $base", "Frontend: $($report.frontend_url)", "")
foreach ($entry in $results.GetEnumerator()) { $lines += "$($entry.Key): $($entry.Value.passed) - $($entry.Value.detail)" }
foreach ($warning in $warnings) { $lines += "WARNING: $warning" }
$lines | Set-Content -LiteralPath $textPath -Encoding UTF8
Write-Host "JSON report: $jsonPath"
Write-Host "Text report: $textPath"
if (-not $report.success) { exit 1 }
