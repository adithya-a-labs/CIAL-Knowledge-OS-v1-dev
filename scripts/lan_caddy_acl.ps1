[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet("Apply", "Verify")]
    [string]$Mode,

    [Parameter(Mandatory)]
    [string]$RootPath,

    [Parameter(Mandatory)]
    [ValidatePattern("^S-\d(?:-\d+)+$")]
    [string]$CurrentUserSid
)

$ErrorActionPreference = "Stop"
$allowedSidValues = @(
    $CurrentUserSid,
    "S-1-5-18",       # SYSTEM
    "S-1-5-32-544"    # Built-in Administrators
)
$allowedSidSet = [System.Collections.Generic.HashSet[string]]::new(
    [string[]]$allowedSidValues,
    [System.StringComparer]::OrdinalIgnoreCase
)

function Get-StateItems {
    param([string]$Path)

    $root = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    @($root) + @(
        Get-ChildItem -LiteralPath $root.FullName -Force -Recurse -ErrorAction Stop
    )
}

function Set-ExactStateAcl {
    param([System.IO.FileSystemInfo]$Item)

    $acl = Get-Acl -LiteralPath $Item.FullName
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($existingRule in @($acl.Access)) {
        [void]$acl.RemoveAccessRuleSpecific($existingRule)
    }

    $inheritance = if ($Item.PSIsContainer) {
        [System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
        [System.Security.AccessControl.InheritanceFlags]::ObjectInherit
    }
    else {
        [System.Security.AccessControl.InheritanceFlags]::None
    }
    foreach ($sidValue in $allowedSidValues) {
        $sid = [System.Security.Principal.SecurityIdentifier]::new($sidValue)
        $rule = [System.Security.AccessControl.FileSystemAccessRule]::new(
            $sid,
            [System.Security.AccessControl.FileSystemRights]::FullControl,
            $inheritance,
            [System.Security.AccessControl.PropagationFlags]::None,
            [System.Security.AccessControl.AccessControlType]::Allow
        )
        [void]$acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $Item.FullName -AclObject $acl
}

function Test-ExactStateAcl {
    param([System.IO.FileSystemInfo[]]$Items)

    foreach ($item in $Items) {
        $acl = Get-Acl -LiteralPath $item.FullName
        if (-not $acl.AreAccessRulesProtected) {
            return $false
        }
        $seen = [System.Collections.Generic.HashSet[string]]::new(
            [System.StringComparer]::OrdinalIgnoreCase
        )
        foreach ($rule in @($acl.Access)) {
            $sid = $rule.IdentityReference.Translate(
                [System.Security.Principal.SecurityIdentifier]
            ).Value
            if (
                $rule.IsInherited -or
                -not $allowedSidSet.Contains($sid) -or
                $rule.AccessControlType -ne
                    [System.Security.AccessControl.AccessControlType]::Allow -or
                ($rule.FileSystemRights -band
                    [System.Security.AccessControl.FileSystemRights]::FullControl) -ne
                    [System.Security.AccessControl.FileSystemRights]::FullControl
            ) {
                return $false
            }
            [void]$seen.Add($sid)
        }
        foreach ($requiredSid in $allowedSidValues) {
            if (-not $seen.Contains($requiredSid)) {
                return $false
            }
        }
    }
    return $true
}

if (-not (Test-Path -LiteralPath $RootPath -PathType Container)) {
    throw "The app-owned Caddy state directory is unavailable."
}

$items = @(Get-StateItems -Path $RootPath)
if ($Mode -eq "Apply") {
    foreach ($item in $items) {
        Set-ExactStateAcl -Item $item
    }
    $items = @(Get-StateItems -Path $RootPath)
}

if (-not (Test-ExactStateAcl -Items $items)) {
    throw "The app-owned Caddy state directory ACL is not restricted."
}

[pscustomobject]@{
    verified = $true
    item_count = $items.Count
    allowed_principal_count = $allowedSidValues.Count
} | ConvertTo-Json -Compress
