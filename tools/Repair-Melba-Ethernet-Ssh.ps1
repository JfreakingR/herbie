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
$installer = Join-Path $PSScriptRoot 'Install-Melba-SshKey-OneShot.ps1'
$agentPub = 'C:\Users\Phyllis\.ssh\pal_melba_agent_ed25519.pub'
$originalPub = 'C:\Users\Phyllis\.ssh\pal_melba_ed25519.pub'

foreach ($requiredPath in @($networkPath, $metaPath, $cmdlinePath, $userDataPath, $installer, $agentPub, $originalPub)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Missing required file: $requiredPath"
    }
}

$volume = Get-Volume -DriveLetter $BootDrive.TrimEnd(':')
if ($volume.FileSystemLabel -ne 'bootfs' -or $volume.FileSystem -ne 'FAT32') {
    throw "Drive $BootDrive is not the Melba bootfs partition."
}

function Get-PublicKeyBody([string]$path) {
    $parts = (Get-Content -LiteralPath $path -Raw).Trim() -split '\s+'
    if ($parts.Count -lt 2 -or $parts[0] -ne 'ssh-ed25519') {
        throw "Not a valid Ed25519 public key: $path"
    }
    return ($parts[0] + ' ' + $parts[1])
}

$agentKey = Get-PublicKeyBody $agentPub
$originalKey = Get-PublicKeyBody $originalPub

$existingUserData = Get-Content -LiteralPath $userDataPath
$passwordLine = $existingUserData | Where-Object { $_ -match '^\s+passwd:' } | Select-Object -First 1
if (-not $passwordLine) {
    throw 'Existing Melba password hash was not found.'
}
$passwordHash = (($passwordLine -replace '^\s+passwd:\s*', '').Trim()).Trim('"')
if ($passwordHash -notmatch '^\$') {
    throw 'Existing Melba password hash has an unexpected format.'
}

$networkConfig = @"
network:
  version: 2
  renderer: NetworkManager
  ethernets:
    eth0:
      dhcp4: true
      dhcp6: true
      optional: true
      link-local: [ ipv4, ipv6 ]
"@

$instanceId = 'pal-melba-ethernet-' + (Get-Date -Format 'yyyyMMddHHmmss')
$metaData = @"
instance-id: $instanceId
local-hostname: Melba
"@

$userData = @"
#cloud-config
manage_resolv_conf: false

hostname: Melba
manage_etc_hosts: true
timezone: America/New_York
keyboard:
  model: pc105
  layout: "us"
user:
  name: jfreakingr
  shell: /bin/bash
  lock_passwd: false
  passwd: "$passwordHash"
  ssh_authorized_keys:
    - "$agentKey pal-melba-agent"
    - "$originalKey pal-melba"
  sudo: ALL=(ALL) NOPASSWD:ALL
ssh_pwauth: false

runcmd:
  - [ sh, -c, "systemctl enable --now ssh; systemctl enable --now avahi-daemon || true" ]
"@

$utf8NoBom = New-Object Text.UTF8Encoding($false)
[IO.File]::WriteAllText($networkPath, $networkConfig.Replace("`r`n", "`n") + "`n", $utf8NoBom)
[IO.File]::WriteAllText($metaPath, $metaData.Replace("`r`n", "`n"), $utf8NoBom)
[IO.File]::WriteAllText($userDataPath, $userData.Replace("`r`n", "`n"), $utf8NoBom)

& $installer -BootDrive $BootDrive -PublicKeyPath @($agentPub, $originalPub)
if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
    throw "SSH one-shot installer failed with exit code $LASTEXITCODE"
}

$writtenNetwork = Get-Content -LiteralPath $networkPath -Raw
$writtenUserData = Get-Content -LiteralPath $userDataPath -Raw
$writtenMeta = Get-Content -LiteralPath $metaPath -Raw
$writtenCmdline = Get-Content -LiteralPath $cmdlinePath -Raw
$writtenFirstRun = Get-Content -LiteralPath (Join-Path $bootRoot 'firstrun.sh') -Raw

$checks = [ordered]@{
    BootPartition = $BootDrive
    EthernetOnlyNetwork = (
        $writtenNetwork.Contains('renderer: NetworkManager') -and
        $writtenNetwork.Contains('eth0:') -and
        $writtenNetwork.Contains('link-local: [ ipv4, ipv6 ]') -and
        ($writtenNetwork -notmatch '(?m)^\s*wifis:') -and
        ($writtenNetwork -notmatch '(?m)^\s*wlan0:') -and
        ($writtenNetwork -notmatch '(?m)^\s*password:') -and
        ($writtenNetwork -notmatch '(?m)^\s*access-points:')
    )
    BothPublicKeysInUserData = $writtenUserData.Contains($agentKey) -and $writtenUserData.Contains($originalKey)
    BothPublicKeysInOneShot = $writtenFirstRun.Contains($agentKey) -and $writtenFirstRun.Contains($originalKey)
    FreshEthernetInstance = $writtenMeta.Contains($instanceId)
    SshFlagPresent = (Test-Path -LiteralPath (Join-Path $bootRoot 'ssh'))
    OneShotArmed = $writtenCmdline.Contains('systemd.run=/boot/firmware/firstrun.sh')
    PasswordAuthDisabled = $writtenUserData.Contains('ssh_pwauth: false')
    ConfigurationVerified = $false
}
$checks.ConfigurationVerified = $checks.EthernetOnlyNetwork -and $checks.BothPublicKeysInUserData -and $checks.BothPublicKeysInOneShot -and $checks.FreshEthernetInstance -and $checks.SshFlagPresent -and $checks.OneShotArmed -and $checks.PasswordAuthDisabled

[pscustomobject]$checks | Format-List
if (-not $checks.ConfigurationVerified) {
    throw 'Melba Ethernet/SSH repair verification failed.'
}
