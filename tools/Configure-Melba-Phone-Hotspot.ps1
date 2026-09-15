[CmdletBinding()]
param(
    [string]$BootDrive = 'F:'
)

$ErrorActionPreference = 'Stop'

function Get-UiValueAfterLabel {
    param(
        [System.Xml.XmlNode[]]$Nodes,
        [string]$Label
    )

    for ($index = 0; $index -lt $Nodes.Count; $index++) {
        if ([string]$Nodes[$index].text -eq $Label) {
            for ($next = $index + 1; $next -lt [Math]::Min($index + 10, $Nodes.Count); $next++) {
                $candidate = [string]$Nodes[$next].text
                if ($candidate -and $candidate -ne $Label) {
                    return $candidate
                }
            }
        }
    }

    throw "Could not find the value following '$Label' on the phone."
}

$bootRoot = "$($BootDrive.TrimEnd('\\'))\\"
$networkPath = Join-Path $bootRoot 'network-config'
$metaPath = Join-Path $bootRoot 'meta-data'
$cmdlinePath = Join-Path $bootRoot 'cmdline.txt'
$configPath = Join-Path $bootRoot 'config.txt'

foreach ($requiredPath in @($cmdlinePath, $configPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "The selected drive is not Melba's boot partition: missing $requiredPath"
    }
}

$adb = (Resolve-Path (Join-Path $PSScriptRoot 'scrcpy-win64-v4.1\scrcpy-win64-v4.1\adb.exe')).Path
$deviceState = (& $adb get-state 2>$null | Select-Object -First 1).Trim()
if ($deviceState -ne 'device') {
    throw 'The authorized Galaxy phone is not connected through ADB.'
}

& $adb shell uiautomator dump /sdcard/pal_hotspot_detail.xml | Out-Null
$rawXml = (& $adb exec-out cat /sdcard/pal_hotspot_detail.xml 2>$null) -join "`n"
if (-not $rawXml) {
    throw 'Could not read the hotspot details from the phone.'
}

[xml]$ui = $rawXml
$nodes = @($ui.SelectNodes('//node'))
$ssid = Get-UiValueAfterLabel -Nodes $nodes -Label 'Network name'
$password = Get-UiValueAfterLabel -Nodes $nodes -Label 'Password'
$band = Get-UiValueAfterLabel -Nodes $nodes -Label 'Band'

if ($band -notmatch '^2\.4 GHz$') {
    throw 'The phone hotspot is not set to 2.4 GHz.'
}
if ($password.Length -lt 8) {
    throw 'The phone hotspot password is unexpectedly short.'
}

$salt = [Text.Encoding]::UTF8.GetBytes($ssid)
$derive = New-Object System.Security.Cryptography.Rfc2898DeriveBytes($password, $salt, 4096)
try {
    $pmk = -join ($derive.GetBytes(32) | ForEach-Object { $_.ToString('x2') })
}
finally {
    $derive.Dispose()
}

$escapedSsid = $ssid.Replace('\\', '\\\\').Replace('"', '\"')
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
        "$escapedSsid":
          password: "$pmk"
      optional: true
"@

if (Test-Path -LiteralPath $networkPath) {
    Copy-Item -LiteralPath $networkPath -Destination "$networkPath.pre-phone-hotspot.bak" -Force
}

$instanceId = 'pal-melba-hotspot-' + (Get-Date -Format 'yyyyMMddHHmmss')
$metaData = "instance-id: $instanceId`nlocal-hostname: Melba`n"
$cmdline = (Get-Content -LiteralPath $cmdlinePath -Raw).Trim()
if ($cmdline -match 'ds=nocloud;i=[^ ]+') {
    $cmdline = $cmdline -replace 'ds=nocloud;i=[^ ]+', "ds=nocloud;i=$instanceId"
}
else {
    $cmdline += " ds=nocloud;i=$instanceId"
}

$utf8NoBom = New-Object Text.UTF8Encoding($false)
[IO.File]::WriteAllText($networkPath, $networkConfig.TrimStart() + "`n", $utf8NoBom)
[IO.File]::WriteAllText($metaPath, $metaData, $utf8NoBom)
[IO.File]::WriteAllText($cmdlinePath, $cmdline + "`n", $utf8NoBom)

$written = Get-Content -LiteralPath $networkPath -Raw
$checks = [ordered]@{
    BootPartition = (Split-Path -Qualifier $networkPath)
    HotspotBand = $band
    SsidLength = $ssid.Length
    PlaintextPasswordStored = $written.Contains($password)
    DerivedKeyStored = ($written -match 'password: "[0-9a-f]{64}"')
    NewCloudInitIdentity = ((Get-Content -LiteralPath $cmdlinePath -Raw) -match [regex]::Escape($instanceId))
    ConfigurationVerified = $false
}
$checks.ConfigurationVerified = (-not $checks.PlaintextPasswordStored) -and $checks.DerivedKeyStored -and $checks.NewCloudInitIdentity

[pscustomobject]$checks | Format-List
if (-not $checks.ConfigurationVerified) {
    throw 'Melba hotspot configuration verification failed.'
}
