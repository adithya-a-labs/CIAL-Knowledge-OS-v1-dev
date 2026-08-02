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
$Group = "CIAL Knowledge OS LAN"
$HttpRule = "CIAL-LAN-HTTP"
$MdnsRule = "CIAL-LAN-MDNS"

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Remove-CialRule {
    param([string]$Name)
    Get-NetFirewallRule -DisplayName $Name -ErrorAction SilentlyContinue |
        Where-Object { $_.Group -eq $Group } |
        Remove-NetFirewallRule -ErrorAction Stop
}

if ($Mode -eq "Inspect") {
    $rules = @(Get-NetFirewallRule -Group $Group -ErrorAction SilentlyContinue)
    [pscustomobject]@{
        mode = "inspect"
        administrator = Test-Administrator
        owned_rule_count = $rules.Count
        owned_rule_names = @($rules | ForEach-Object { $_.DisplayName } | Where-Object { $_ })
        proposed_http = [pscustomobject]@{
            local_address = $LocalAddress
            remote_address = $RemoteSubnet
            local_port = $HttpPort
            interface_alias = $InterfaceAlias
        }
    } | ConvertTo-Json -Depth 4
    exit 0
}

if (-not (Test-Administrator)) {
    throw "CIAL LAN firewall management requires an Administrator PowerShell session."
}

if ($Mode -eq "Remove") {
    Remove-CialRule -Name $HttpRule
    Remove-CialRule -Name $MdnsRule
    [pscustomobject]@{ mode = "remove"; removed = @($HttpRule, $MdnsRule) } | ConvertTo-Json
    exit 0
}

if (-not $LocalAddress -or -not $RemoteSubnet -or -not $InterfaceAlias) {
    throw "Apply requires LocalAddress, RemoteSubnet, and InterfaceAlias."
}

Remove-CialRule -Name $HttpRule
New-NetFirewallRule -DisplayName $HttpRule -Group $Group `
    -Description "CIAL-owned hotspot gateway rule. Safe to remove with the CIAL LAN stop command." `
    -Direction Inbound -Action Allow -Enabled True -Profile Any `
    -Protocol TCP -LocalPort $HttpPort -LocalAddress $LocalAddress `
    -RemoteAddress $RemoteSubnet -InterfaceAlias $InterfaceAlias | Out-Null

Remove-CialRule -Name $MdnsRule
if ($DiscoveryProgram) {
    New-NetFirewallRule -DisplayName $MdnsRule -Group $Group `
        -Description "CIAL-owned interface-scoped mDNS discovery rule." `
        -Direction Inbound -Action Allow -Enabled True -Profile Any `
        -Protocol UDP -LocalPort 5353 -LocalAddress $LocalAddress `
        -RemoteAddress $RemoteSubnet -InterfaceAlias $InterfaceAlias `
        -Program $DiscoveryProgram | Out-Null
}

$http = Get-NetFirewallRule -DisplayName $HttpRule -ErrorAction Stop |
    Where-Object { $_.Group -eq $Group } |
    Select-Object -First 1
if ($null -eq $http) { throw "The CIAL-owned HTTP firewall rule was not found after creation." }
$httpPort = $http | Get-NetFirewallPortFilter
$httpAddress = $http | Get-NetFirewallAddressFilter
$httpInterface = $http | Get-NetFirewallInterfaceFilter
$valid = $http.Enabled -eq "True" -and
    $http.Direction -eq "Inbound" -and
    $http.Action -eq "Allow" -and
    [string]$http.Profile -eq "Any" -and
    $httpPort.Protocol -eq "TCP" -and
    [string]$httpPort.LocalPort -eq [string]$HttpPort -and
    $httpAddress.LocalAddress -contains $LocalAddress -and
    $httpAddress.RemoteAddress -contains $RemoteSubnet -and
    $httpInterface.InterfaceAlias -contains $InterfaceAlias
if (-not $valid) { throw "Effective CIAL LAN HTTP firewall rule did not match its requested scope." }

if ($DiscoveryProgram) {
    $mdns = Get-NetFirewallRule -DisplayName $MdnsRule -ErrorAction Stop |
        Where-Object { $_.Group -eq $Group } |
        Select-Object -First 1
    $mdnsPort = $mdns | Get-NetFirewallPortFilter
    $mdnsAddress = $mdns | Get-NetFirewallAddressFilter
    $mdnsInterface = $mdns | Get-NetFirewallInterfaceFilter
    $mdnsApplication = $mdns | Get-NetFirewallApplicationFilter
    $mdnsValid = $mdns.Enabled -eq "True" -and
        $mdns.Direction -eq "Inbound" -and
        $mdns.Action -eq "Allow" -and
        [string]$mdns.Profile -eq "Any" -and
        $mdnsPort.Protocol -eq "UDP" -and
        [string]$mdnsPort.LocalPort -eq "5353" -and
        $mdnsAddress.LocalAddress -contains $LocalAddress -and
        $mdnsAddress.RemoteAddress -contains $RemoteSubnet -and
        $mdnsInterface.InterfaceAlias -contains $InterfaceAlias -and
        [string]$mdnsApplication.Program -eq [string]$DiscoveryProgram
    if (-not $mdnsValid) { throw "Effective CIAL LAN mDNS firewall rule did not match its requested scope." }
}

[pscustomobject]@{
    mode = "apply"
    verified = $true
    rule_names = if ($DiscoveryProgram) { @($HttpRule, $MdnsRule) } else { @($HttpRule) }
    local_address = $LocalAddress
    remote_subnet = $RemoteSubnet
    http_port = $HttpPort
} | ConvertTo-Json -Depth 3
