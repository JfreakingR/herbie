[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$interfaceOutput = & netsh.exe wlan show interfaces
$connectedBlock = $interfaceOutput -join "`n"
$ssidMatch = [regex]::Match($connectedBlock,'(?m)^\s*SSID\s*:\s*(.+?)\s*$')
if (-not $ssidMatch.Success) {
    throw 'No connected Windows Wi-Fi network was found.'
}
$ssid = $ssidMatch.Groups[1].Value.Trim()

$profileOutput = & netsh.exe wlan show profile name="$ssid" key=clear
$profileText = $profileOutput -join "`n"
$keyMatch = [regex]::Match($profileText,'(?m)^\s*Key Content\s*:\s*(.+?)\s*$')
if (-not $keyMatch.Success) {
    throw 'The connected Wi-Fi profile does not contain a saved security key.'
}
$wifiKey = $keyMatch.Groups[1].Value.Trim()

$ssidBytes = [System.Text.Encoding]::UTF8.GetBytes($ssid)
$derive = [System.Security.Cryptography.Rfc2898DeriveBytes]::new(
    $wifiKey,
    $ssidBytes,
    4096,
    [System.Security.Cryptography.HashAlgorithmName]::SHA1
)
try {
    $pmk = ([BitConverter]::ToString($derive.GetBytes(32))).Replace('-','').ToLowerInvariant()
} finally {
    $derive.Dispose()
}
if ($pmk -notmatch '^[0-9a-f]{64}$') {
    throw 'Wi-Fi key derivation failed.'
}

function ConvertTo-YamlDoubleQuotedValue {
    param([Parameter(Mandatory)][string]$Value)
    return $Value.Replace('\','\\').Replace('"','\"')
}

$yamlSsid = ConvertTo-YamlDoubleQuotedValue -Value $ssid
$networkConfig = @"
network:
  version: 2
  ethernets:
    eth0:
      dhcp4: true
      dhcp6: true
      optional: true
  wifis:
    wlan0:
      dhcp4: true
      regulatory-domain: "US"
      access-points:
        "$yamlSsid":
          password: "$pmk"
      optional: true
"@

[System.IO.File]::WriteAllText(
    'F:\network-config',
    $networkConfig,
    [System.Text.UTF8Encoding]::new($false)
)

$written = Get-Content -LiteralPath 'F:\network-config' -Raw
if ($written -notmatch 'regulatory-domain: "US"') {
    throw 'Wi-Fi regulatory domain was not written.'
}
if ($written -notmatch [regex]::Escape($pmk)) {
    throw 'Derived Wi-Fi key was not written.'
}
if ($written -match [regex]::Escape($wifiKey)) {
    throw 'Plaintext Wi-Fi key was unexpectedly written.'
}

Write-Output 'WIFI_CONFIG_WRITTEN=True'
Write-Output 'PLAINTEXT_PASSWORD_STORED=False'
Write-Output 'ETHERNET_FALLBACK=True'
Write-Output 'COUNTRY=US'
