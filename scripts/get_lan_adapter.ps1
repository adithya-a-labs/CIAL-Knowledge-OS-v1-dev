[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$adapters = @(Get-NetAdapter -IncludeHidden -ErrorAction SilentlyContinue)
$addresses = @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -and $_.PrefixLength })
$profiles = @(Get-NetConnectionProfile -ErrorAction SilentlyContinue)
$natPrefixes = @()
if (Get-Command Get-NetNat -ErrorAction SilentlyContinue) {
    $natPrefixes = @(Get-NetNat -ErrorAction SilentlyContinue |
        ForEach-Object { $_.InternalIPInterfaceAddressPrefix } |
        Where-Object { $_ })
}

$records = foreach ($address in $addresses) {
    $adapter = $adapters | Where-Object { $_.ifIndex -eq $address.InterfaceIndex } | Select-Object -First 1
    if ($null -eq $adapter) { continue }
    $profile = $profiles | Where-Object { $_.InterfaceIndex -eq $address.InterfaceIndex } | Select-Object -First 1
    $matchingNat = $false
    foreach ($prefix in $natPrefixes) {
        try {
            $networkText, $prefixLengthText = $prefix -split "/", 2
            $prefixLength = [int]$prefixLengthText
            $ipBytes = [System.Net.IPAddress]::Parse($address.IPAddress).GetAddressBytes()
            $networkBytes = [System.Net.IPAddress]::Parse($networkText).GetAddressBytes()
            $wholeBytes = [math]::Floor($prefixLength / 8)
            $remainder = $prefixLength % 8
            $same = $true
            for ($i = 0; $i -lt $wholeBytes; $i++) {
                if ($ipBytes[$i] -ne $networkBytes[$i]) { $same = $false; break }
            }
            if ($same -and $remainder -gt 0) {
                $mask = (0xFF -shl (8 - $remainder)) -band 0xFF
                $same = (($ipBytes[$wholeBytes] -band $mask) -eq ($networkBytes[$wholeBytes] -band $mask))
            }
            if ($same) { $matchingNat = $true; break }
        } catch {
            continue
        }
    }

    [pscustomobject]@{
        interface_alias = [string]$adapter.Name
        interface_index = [int]$address.InterfaceIndex
        description = [string]$adapter.InterfaceDescription
        status = [string]$adapter.Status
        media_type = [string]$adapter.MediaType
        address = [string]$address.IPAddress
        prefix_length = [int]$address.PrefixLength
        profile_category = if ($profile) { [string]$profile.NetworkCategory } else { "" }
        nat = [bool]$matchingNat
        # Wi-Fi Direct identity is useful evidence, but it is not itself proof
        # that Windows Internet Connection Sharing is active.
        ics = $false
        wifi_direct = [bool]($adapter.InterfaceDescription -match "Wi-Fi Direct")
    }
}

ConvertTo-Json -InputObject @($records) -Depth 3 -Compress
