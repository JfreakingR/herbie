[CmdletBinding()]
param(
    [string]$BootDrive = 'F:'
)

$ErrorActionPreference = 'Stop'
$bootRoot = "$($BootDrive.TrimEnd('\\'))\\"
$networkPath = Join-Path $bootRoot 'network-config'
$metaPath = Join-Path $bootRoot 'meta-data'
$cmdlinePath = Join-Path $bootRoot 'cmdline.txt'
$userDataPath = Join-Path $bootRoot 'user-data'
$preseedPath = Join-Path $bootRoot 'rpi-preseed.toml'

foreach ($requiredPath in @($networkPath, $metaPath, $cmdlinePath, $userDataPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "The selected drive is not the expected Melba boot partition: missing $requiredPath"
    }
}

$userData = Get-Content -LiteralPath $userDataPath -Raw
if (-not $userData.TrimStart().StartsWith('#cloud-config')) {
    throw 'user-data is missing the mandatory #cloud-config header.'
}

$network = Get-Content -LiteralPath $networkPath -Raw
if ($network -notmatch '(?m)^\s{2}wifis:\s*$') {
    throw 'network-config has no wifis section.'
}
if ($network -notmatch '(?m)^\s{4}renderer:\s*NetworkManager\s*$') {
    $network = $network -replace '(?m)^(\s{2}wifis:\s*)$', "$1`n    renderer: NetworkManager"
}

$instanceId = 'pal-melba-hotspot-' + (Get-Date -Format 'yyyyMMddHHmmss')
$metaData = "instance-id: $instanceId`nlocal-hostname: Melba`n"
$cmdline = (Get-Content -LiteralPath $cmdlinePath -Raw).Trim()
$cmdline = ($cmdline -replace '\s*ds=nocloud;i=[^ ]+', '').Trim()

$utf8NoBom = New-Object Text.UTF8Encoding($false)
[IO.File]::WriteAllText($networkPath, $network.TrimStart() + "`n", $utf8NoBom)
[IO.File]::WriteAllText($metaPath, $metaData, $utf8NoBom)
[IO.File]::WriteAllText($cmdlinePath, $cmdline + "`n", $utf8NoBom)

if (Test-Path -LiteralPath $preseedPath) {
    Move-Item -LiteralPath $preseedPath -Destination (Join-Path $bootRoot 'rpi-preseed.toml.unused') -Force
}

$writtenNetwork = Get-Content -LiteralPath $networkPath -Raw
$writtenMeta = Get-Content -LiteralPath $metaPath -Raw
$writtenCmdline = Get-Content -LiteralPath $cmdlinePath -Raw
$checks = [ordered]@{
    BootPartition = (Split-Path -Qualifier $networkPath)
    CloudConfigHeader = (Get-Content -LiteralPath $userDataPath -Raw).TrimStart().StartsWith('#cloud-config')
    NetworkManagerRenderer = ($writtenNetwork -match '(?m)^\s{4}renderer:\s*NetworkManager\s*$')
    WlanConfigurationPresent = ($writtenNetwork -match '(?m)^\s{4}wlan0:\s*$')
    DerivedKeyPresent = ($writtenNetwork -match '(?m)^\s*password:\s*"[0-9a-f]{64}"\s*$')
    FreshInstanceIdentity = $writtenMeta.Contains($instanceId)
    ManualDatasourceOverrideAbsent = (-not $writtenCmdline.Contains('ds=nocloud'))
    CompetingPreseedRetired = (-not (Test-Path -LiteralPath $preseedPath))
    ConfigurationVerified = $false
}
$checks.ConfigurationVerified = $checks.CloudConfigHeader -and $checks.NetworkManagerRenderer -and $checks.WlanConfigurationPresent -and $checks.DerivedKeyPresent -and $checks.FreshInstanceIdentity -and $checks.ManualDatasourceOverrideAbsent -and $checks.CompetingPreseedRetired

[pscustomobject]$checks | Format-List
if (-not $checks.ConfigurationVerified) {
    throw 'Corrected Melba cloud-init verification failed.'
}
