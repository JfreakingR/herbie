[CmdletBinding()]
param(
    [string]$BootDrive = 'F:'
)

$ErrorActionPreference = 'Stop'

$bootRoot = "$($BootDrive.TrimEnd('\\'))\\"
$configPath = Join-Path $bootRoot 'config.txt'
$cmdlinePath = Join-Path $bootRoot 'cmdline.txt'
$networkPath = Join-Path $bootRoot 'network-config'
$preseedPath = Join-Path $bootRoot 'rpi-preseed.toml'

foreach ($requiredPath in @($configPath, $cmdlinePath, $networkPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "The selected drive is not the expected Melba boot partition: missing $requiredPath"
    }
}

$networkConfig = Get-Content -LiteralPath $networkPath -Raw
$ssidMatch = [regex]::Match($networkConfig, '(?m)^\s{8}"(?<ssid>(?:\\.|[^"])*)":\s*$')
$keyMatch = [regex]::Match($networkConfig, '(?m)^\s*password:\s*"(?<key>[0-9a-fA-F]{64})"\s*$')
if (-not $ssidMatch.Success -or -not $keyMatch.Success) {
    throw 'Could not recover the verified hotspot identity and derived key from network-config.'
}

$ssid = $ssidMatch.Groups['ssid'].Value.Replace('\"', '"').Replace('\\\\', '\\')
$derivedKey = $keyMatch.Groups['key'].Value.ToLowerInvariant()
$tomlSsid = $ssid.Replace('\\', '\\\\').Replace('"', '\"')

$preseed = @"
config_version = "1.0"

[wlan]
ssid = "$tomlSsid"
password = "$derivedKey"
password_encrypted = true
hidden = false
country = "US"
"@

$cmdlineOriginal = (Get-Content -LiteralPath $cmdlinePath -Raw).Trim()
$cmdlineUpdated = ($cmdlineOriginal -replace '\s*ds=nocloud;i=[^ ]+', '').Trim()

$utf8NoBom = New-Object Text.UTF8Encoding($false)
[IO.File]::WriteAllText($preseedPath, $preseed.TrimStart() + "`n", $utf8NoBom)
[IO.File]::WriteAllText($cmdlinePath, $cmdlineUpdated + "`n", $utf8NoBom)

$written = Get-Content -LiteralPath $preseedPath -Raw
$checks = [ordered]@{
    BootPartition = (Split-Path -Qualifier $preseedPath)
    NativePreseedPresent = (Test-Path -LiteralPath $preseedPath)
    SsidLength = $ssid.Length
    DerivedKeyStored = ($written -match '(?m)^password = "[0-9a-f]{64}"$')
    KeyMarkedEncrypted = ($written -match '(?m)^password_encrypted = true$')
    CountrySet = ($written -match '(?m)^country = "US"$')
    OldCloudInitBootSelectorRemoved = (-not ((Get-Content -LiteralPath $cmdlinePath -Raw) -match 'ds=nocloud'))
    ConfigurationVerified = $false
}
$checks.ConfigurationVerified = $checks.NativePreseedPresent -and $checks.DerivedKeyStored -and $checks.KeyMarkedEncrypted -and $checks.CountrySet -and $checks.OldCloudInitBootSelectorRemoved

[pscustomobject]$checks | Format-List
if (-not $checks.ConfigurationVerified) {
    throw 'Native Raspberry Pi preseed verification failed.'
}
