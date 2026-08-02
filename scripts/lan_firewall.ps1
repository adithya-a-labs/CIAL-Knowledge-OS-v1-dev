[CmdletBinding()]
param(
    [ValidateSet("Inspect", "Apply", "Remove")]
    [string]$Mode = "Inspect",
    [string]$LocalAddress,
    [string]$RemoteSubnet,
    [ValidateRange(1, 65535)]
    [int]$HttpPort = 80,
    [string]$InterfaceAlias,
    [string]$DiscoveryProgram
)

$ErrorActionPreference = "Stop"
$FirewallGroupName = "CIAL Knowledge OS LAN"
$HttpRuleName = "CIAL-LAN-HTTP"
$MdnsRuleName = "CIAL-LAN-MDNS"

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function ConvertTo-NormalizedStrings {
    param([object]$Value)
    return @(
        @($Value) |
            Where-Object { $null -ne $_ } |
            ForEach-Object { ([string]$_).Trim() } |
            Where-Object { $_ }
    )
}

function ConvertTo-CanonicalProtocol {
    param([object]$Value)
    $protocolText = ([string]$Value).Trim().ToUpperInvariant()
    if ($protocolText -eq "6") { return "TCP" }
    if ($protocolText -eq "17") { return "UDP" }
    return $protocolText
}

function Test-CialEnumValue {
    param(
        [object]$Actual,
        [string]$ExpectedName,
        [string]$ExpectedNumeric
    )
    foreach ($candidate in @(ConvertTo-NormalizedStrings -Value $Actual)) {
        if (
            $candidate.Equals($ExpectedName, [StringComparison]::OrdinalIgnoreCase) -or
            $candidate -eq $ExpectedNumeric
        ) {
            return $true
        }
    }
    return $false
}

function ConvertTo-CanonicalIpv4Scope {
    param([string]$Value)
    $scopeText = $Value.Trim()
    if (-not $scopeText) { return "" }
    if ($scopeText.Equals("Any", [StringComparison]::OrdinalIgnoreCase)) {
        return "any"
    }
    if ($scopeText -notmatch "^([^/]+)(?:/(.+))?$") {
        return $scopeText.ToLowerInvariant()
    }
    try {
        $addressText = $Matches[1]
        $suffixText = $Matches[2]
        $ip = [Net.IPAddress]::Parse($addressText)
        if ($ip.AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork) {
            return $scopeText.ToLowerInvariant()
        }
        $prefix = 32
        if ($suffixText) {
            if ($suffixText -match "^\d+$") {
                $prefix = [int]$suffixText
            }
            else {
                $mask = [Net.IPAddress]::Parse($suffixText)
                $bits = ($mask.GetAddressBytes() | ForEach-Object {
                    [Convert]::ToString($_, 2).PadLeft(8, "0")
                }) -join ""
                if ($bits -notmatch "^1*0*$") { return $scopeText.ToLowerInvariant() }
                $prefix = ($bits.ToCharArray() | Where-Object { $_ -eq "1" }).Count
            }
        }
        if ($prefix -lt 0 -or $prefix -gt 32) { return $scopeText.ToLowerInvariant() }
        $bytes = $ip.GetAddressBytes()
        [uint32]$ipValue = ([uint32]$bytes[0] -shl 24) -bor
            ([uint32]$bytes[1] -shl 16) -bor
            ([uint32]$bytes[2] -shl 8) -bor [uint32]$bytes[3]
        [uint32]$maskValue = if ($prefix -eq 0) {
            0
        } else {
            [uint32]::MaxValue -shl (32 - $prefix)
        }
        [uint32]$networkValue = $ipValue -band $maskValue
        $networkAddress = "{0}.{1}.{2}.{3}" -f (
            ($networkValue -shr 24) -band 255
        ), (($networkValue -shr 16) -band 255), (
            ($networkValue -shr 8) -band 255
        ), ($networkValue -band 255)
        return "$networkAddress/$prefix"
    }
    catch {
        return $scopeText.ToLowerInvariant()
    }
}

function Test-NormalizedContains {
    param([object]$Actual, [string]$Expected)
    foreach ($candidate in @(ConvertTo-NormalizedStrings -Value $Actual)) {
        if ($candidate.Equals($Expected, [StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }
    return $false
}

function Test-ScopeContains {
    param([object]$Actual, [string]$Expected)
    $expectedScope = ConvertTo-CanonicalIpv4Scope -Value $Expected
    foreach ($candidate in @(ConvertTo-NormalizedStrings -Value $Actual)) {
        if ((ConvertTo-CanonicalIpv4Scope -Value $candidate) -eq $expectedScope) {
            return $true
        }
    }
    return $false
}

function Get-CialContractState {
    param(
        [int]$HttpRuleCount,
        [int]$MdnsRuleCount,
        [bool]$MdnsRequired,
        [bool]$HttpValid,
        [bool]$MdnsValid
    )
    $presentCount = $HttpRuleCount + $MdnsRuleCount
    $requiredCount = if ($MdnsRequired) { 2 } else { 1 }
    if ($presentCount -eq 0) { return "absent" }
    if ($HttpRuleCount -eq 0 -or ($MdnsRequired -and $MdnsRuleCount -eq 0)) {
        return "partial"
    }
    if (
        $presentCount -eq $requiredCount -and
        $HttpRuleCount -eq 1 -and
        $MdnsRuleCount -eq [int]$MdnsRequired -and
        $HttpValid -and $MdnsValid
    ) {
        return "ready"
    }
    return "mismatched"
}

function Remove-CialRule {
    param([string]$RuleName)
    Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue |
        Where-Object { $_.Group -eq $FirewallGroupName } |
        Remove-NetFirewallRule -ErrorAction Stop
}

function Test-CialRuleContract {
    param(
        [object]$Snapshot,
        [string]$ExpectedProtocol,
        [string]$ExpectedPort,
        [string]$ExpectedLocalAddress,
        [string]$ExpectedRemoteSubnet,
        [string]$ExpectedInterfaceAlias,
        [string]$ExpectedProgram = ""
    )
    if ($null -eq $Snapshot) { return $false }
    $selectedRule = $Snapshot.rule
    $portFilter = $Snapshot.port_filter
    $addressFilter = $Snapshot.address_filter
    $interfaceFilter = $Snapshot.interface_filter
    $enabled = Test-CialEnumValue -Actual $selectedRule.Enabled -ExpectedName "True" -ExpectedNumeric "1"
    $direction = Test-CialEnumValue -Actual $selectedRule.Direction -ExpectedName "Inbound" -ExpectedNumeric "1"
    $action = Test-CialEnumValue -Actual $selectedRule.Action -ExpectedName "Allow" -ExpectedNumeric "2"
    $profile = Test-CialEnumValue -Actual $selectedRule.Profile -ExpectedName "Any" -ExpectedNumeric "0"
    $protocol = (ConvertTo-CanonicalProtocol -Value $portFilter.Protocol) -eq $ExpectedProtocol
    $port = Test-NormalizedContains -Actual $portFilter.LocalPort -Expected $ExpectedPort
    $localScope = Test-ScopeContains -Actual $addressFilter.LocalAddress -Expected $ExpectedLocalAddress
    $remoteScope = Test-ScopeContains -Actual $addressFilter.RemoteAddress -Expected $ExpectedRemoteSubnet
    $interface = Test-NormalizedContains -Actual $interfaceFilter.InterfaceAlias -Expected $ExpectedInterfaceAlias
    $program = $true
    if ($ExpectedProgram) {
        $actualPrograms = @(ConvertTo-NormalizedStrings -Value $Snapshot.application_filter.Program)
        $program = $actualPrograms.Count -eq 1 -and
            [IO.Path]::GetFullPath($actualPrograms[0]).Equals(
                [IO.Path]::GetFullPath($ExpectedProgram),
                [StringComparison]::OrdinalIgnoreCase
            )
    }
    return $enabled -and $direction -and $action -and $profile -and
        $protocol -and $port -and $localScope -and $remoteScope -and
        $interface -and $program
}

function Get-CialFirewallContract {
    param(
        [string]$ExpectedLocalAddress,
        [string]$ExpectedRemoteSubnet,
        [int]$ExpectedHttpPort,
        [string]$ExpectedInterfaceAlias,
        [string]$ExpectedDiscoveryProgram
    )
    $httpRules = @(
        Get-NetFirewallRule -DisplayName $HttpRuleName -ErrorAction SilentlyContinue |
            Where-Object { $_.Group -eq $FirewallGroupName }
    )
    $httpRule = $httpRules | Select-Object -First 1
    $httpPortFilter = if ($null -ne $httpRule) { $httpRule | Get-NetFirewallPortFilter } else { $null }
    $httpAddressFilter = if ($null -ne $httpRule) { $httpRule | Get-NetFirewallAddressFilter } else { $null }
    $httpInterfaceFilter = if ($null -ne $httpRule) { $httpRule | Get-NetFirewallInterfaceFilter } else { $null }
    $httpSnapshot = if ($null -ne $httpRule) {
        [pscustomobject]@{
            rule = $httpRule
            port_filter = $httpPortFilter
            address_filter = $httpAddressFilter
            interface_filter = $httpInterfaceFilter
            application_filter = $null
        }
    } else { $null }

    $mdnsRules = @(
        Get-NetFirewallRule -DisplayName $MdnsRuleName -ErrorAction SilentlyContinue |
            Where-Object { $_.Group -eq $FirewallGroupName }
    )
    $mdnsRule = $mdnsRules | Select-Object -First 1
    $mdnsPortFilter = if ($null -ne $mdnsRule) { $mdnsRule | Get-NetFirewallPortFilter } else { $null }
    $mdnsAddressFilter = if ($null -ne $mdnsRule) { $mdnsRule | Get-NetFirewallAddressFilter } else { $null }
    $mdnsInterfaceFilter = if ($null -ne $mdnsRule) { $mdnsRule | Get-NetFirewallInterfaceFilter } else { $null }
    $mdnsApplicationFilter = if ($null -ne $mdnsRule) { $mdnsRule | Get-NetFirewallApplicationFilter } else { $null }
    $mdnsSnapshot = if ($null -ne $mdnsRule) {
        [pscustomobject]@{
            rule = $mdnsRule
            port_filter = $mdnsPortFilter
            address_filter = $mdnsAddressFilter
            interface_filter = $mdnsInterfaceFilter
            application_filter = $mdnsApplicationFilter
        }
    } else { $null }

    $httpValid = Test-CialRuleContract -Snapshot $httpSnapshot `
        -ExpectedProtocol "TCP" -ExpectedPort ([string]$ExpectedHttpPort) `
        -ExpectedLocalAddress $ExpectedLocalAddress `
        -ExpectedRemoteSubnet $ExpectedRemoteSubnet `
        -ExpectedInterfaceAlias $ExpectedInterfaceAlias
    $mdnsRequired = [bool]$ExpectedDiscoveryProgram
    $mdnsValid = if ($mdnsRequired) {
        Test-CialRuleContract -Snapshot $mdnsSnapshot `
            -ExpectedProtocol "UDP" -ExpectedPort "5353" `
            -ExpectedLocalAddress $ExpectedLocalAddress `
            -ExpectedRemoteSubnet $ExpectedRemoteSubnet `
            -ExpectedInterfaceAlias $ExpectedInterfaceAlias `
            -ExpectedProgram $ExpectedDiscoveryProgram
    } else { $null -eq $mdnsRule }
    $httpRuleCount = $httpRules.Count
    $mdnsRuleCount = $mdnsRules.Count
    $contractState = Get-CialContractState `
        -HttpRuleCount $httpRuleCount `
        -MdnsRuleCount $mdnsRuleCount `
        -MdnsRequired $mdnsRequired `
        -HttpValid $httpValid `
        -MdnsValid $mdnsValid
    return [pscustomobject]@{
        state = $contractState
        verified = $contractState -eq "ready"
        http_present = $null -ne $httpRule
        http_valid = [bool]$httpValid
        mdns_required = $mdnsRequired
        mdns_present = $null -ne $mdnsRule
        mdns_valid = [bool]$mdnsValid
    }
}

# Dot-sourcing loads only the pure normalization/verification helpers for
# deterministic tests; normal -File execution continues into the operation.
if ($MyInvocation.InvocationName -eq ".") { return }

if ($Mode -ne "Remove" -and (-not $LocalAddress -or -not $RemoteSubnet -or -not $InterfaceAlias)) {
    [pscustomobject]@{
        mode = $Mode.ToLowerInvariant()
        state = "invalid_request"
        verified = $false
        error_code = "firewall_scope_required"
    } | ConvertTo-Json -Compress
    exit 2
}

$resolvedDiscoveryProgram = ""
if ($DiscoveryProgram) {
    try {
        $resolvedDiscoveryProgram = (Resolve-Path -LiteralPath $DiscoveryProgram -ErrorAction Stop).Path
    }
    catch {
        [pscustomobject]@{
            mode = $Mode.ToLowerInvariant()
            state = "invalid_request"
            verified = $false
            error_code = "discovery_program_unavailable"
        } | ConvertTo-Json -Compress
        exit 2
    }
}

if ($Mode -eq "Inspect") {
    $inspection = Get-CialFirewallContract `
        -ExpectedLocalAddress $LocalAddress `
        -ExpectedRemoteSubnet $RemoteSubnet `
        -ExpectedHttpPort $HttpPort `
        -ExpectedInterfaceAlias $InterfaceAlias `
        -ExpectedDiscoveryProgram $resolvedDiscoveryProgram
    [pscustomobject]@{
        mode = "inspect"
        state = $inspection.state
        verified = $inspection.verified
        administrator = Test-Administrator
        http_present = $inspection.http_present
        http_valid = $inspection.http_valid
        mdns_required = $inspection.mdns_required
        mdns_present = $inspection.mdns_present
        mdns_valid = $inspection.mdns_valid
        local_address = $LocalAddress
        remote_subnet = ConvertTo-CanonicalIpv4Scope -Value $RemoteSubnet
        http_port = $HttpPort
        interface_alias = $InterfaceAlias
    } | ConvertTo-Json -Compress
    exit 0
}

if (-not (Test-Administrator)) {
    [pscustomobject]@{
        mode = $Mode.ToLowerInvariant()
        state = "permission_denied"
        verified = $false
        error_code = "administrator_required"
    } | ConvertTo-Json -Compress
    exit 3
}

if ($Mode -eq "Remove") {
    $existingRuleNames = @(
        Get-NetFirewallRule -Group $FirewallGroupName -ErrorAction SilentlyContinue |
            Where-Object { $_.DisplayName -in @($HttpRuleName, $MdnsRuleName) } |
            ForEach-Object { $_.DisplayName }
    )
    Remove-CialRule -RuleName $HttpRuleName
    Remove-CialRule -RuleName $MdnsRuleName
    [pscustomobject]@{
        mode = "remove"
        state = "absent"
        verified = $true
        removed = @($existingRuleNames)
    } | ConvertTo-Json -Compress
    exit 0
}

$applyPhase = "reconcile"
try {
    Remove-CialRule -RuleName $HttpRuleName
    Remove-CialRule -RuleName $MdnsRuleName
    $applyPhase = "create_http"
    New-NetFirewallRule -DisplayName $HttpRuleName -Group $FirewallGroupName `
        -Description "CIAL-owned hotspot gateway rule. Safe to remove with the CIAL LAN stop command." `
        -Direction Inbound -Action Allow -Enabled True -Profile Any `
        -Protocol TCP -LocalPort $HttpPort -LocalAddress $LocalAddress `
        -RemoteAddress $RemoteSubnet -InterfaceAlias $InterfaceAlias | Out-Null
    if ($resolvedDiscoveryProgram) {
        $applyPhase = "create_mdns"
        New-NetFirewallRule -DisplayName $MdnsRuleName -Group $FirewallGroupName `
            -Description "CIAL-owned interface-scoped mDNS discovery rule." `
            -Direction Inbound -Action Allow -Enabled True -Profile Any `
            -Protocol UDP -LocalPort 5353 -LocalAddress $LocalAddress `
            -RemoteAddress $RemoteSubnet -InterfaceAlias $InterfaceAlias `
            -Program $resolvedDiscoveryProgram | Out-Null
    }
    $applyPhase = "verify"
    $appliedContract = Get-CialFirewallContract `
        -ExpectedLocalAddress $LocalAddress `
        -ExpectedRemoteSubnet $RemoteSubnet `
        -ExpectedHttpPort $HttpPort `
        -ExpectedInterfaceAlias $InterfaceAlias `
        -ExpectedDiscoveryProgram $resolvedDiscoveryProgram
    if (-not $appliedContract.verified) {
        throw [InvalidOperationException]::new("Owned firewall rules did not match the requested contract.")
    }
    [pscustomobject]@{
        mode = "apply"
        state = "ready"
        verified = $true
        rule_names = if ($resolvedDiscoveryProgram) {
            @($HttpRuleName, $MdnsRuleName)
        } else { @($HttpRuleName) }
        local_address = $LocalAddress
        remote_subnet = ConvertTo-CanonicalIpv4Scope -Value $RemoteSubnet
        http_port = $HttpPort
        interface_alias = $InterfaceAlias
    } | ConvertTo-Json -Compress
    exit 0
}
catch {
    try { Remove-CialRule -RuleName $HttpRuleName } catch { }
    try { Remove-CialRule -RuleName $MdnsRuleName } catch { }
    [pscustomobject]@{
        mode = "apply"
        state = "rolled_back"
        verified = $false
        error_code = if ($applyPhase -eq "verify") {
            "firewall_verification_failed"
        } else {
            "firewall_creation_failed"
        }
    } | ConvertTo-Json -Compress
    exit 1
}
