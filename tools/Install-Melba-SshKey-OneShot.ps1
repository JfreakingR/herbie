[CmdletBinding()]
param(
    [string]$BootDrive = 'F:',
    [string[]]$PublicKeyPath = @(
        'C:\Users\Phyllis\.ssh\pal_melba_agent_ed25519.pub',
        'C:\Users\Phyllis\.ssh\pal_melba_ed25519.pub'
    )
)

$ErrorActionPreference = 'Stop'
$bootRoot = "$($BootDrive.TrimEnd('\\'))\\"
$configPath = Join-Path $bootRoot 'config.txt'
$cmdlinePath = Join-Path $bootRoot 'cmdline.txt'
$scriptPath = Join-Path $bootRoot 'firstrun.sh'
$sshFlagPath = Join-Path $bootRoot 'ssh'

foreach ($requiredPath in @($configPath, $cmdlinePath)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Missing required file: $requiredPath"
    }
}

$publicKeys = @()
foreach ($path in $PublicKeyPath) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Missing required file: $path"
    }
    $keyParts = (Get-Content -LiteralPath $path -Raw).Trim() -split '\s+'
    if ($keyParts.Count -lt 2 -or $keyParts[0] -ne 'ssh-ed25519') {
        throw "Not a valid Ed25519 public key: $path"
    }
    $publicKeys += ($keyParts[0] + ' ' + $keyParts[1])
}
if ($publicKeys.Count -lt 1) {
    throw 'At least one Melba public key is required.'
}
$publicKeyLines = ($publicKeys -join "`n")

$scriptTemplate = @'
#!/bin/sh
set -eu
BOOTDIR=/boot/firmware
exec >"$BOOTDIR/pal-ssh-key-install.log" 2>&1
echo "PAL_SSH_KEY_INSTALL_STARTED"
FIRSTUSER=$(getent passwd 1000 | cut -d: -f1)
FIRSTHOME=$(getent passwd 1000 | cut -d: -f6)
FIRSTGROUP=$(id -gn "$FIRSTUSER")
test -n "$FIRSTUSER"
test -d "$FIRSTHOME"
install -o "$FIRSTUSER" -g "$FIRSTGROUP" -m 700 -d "$FIRSTHOME/.ssh"
printf '%s\n' '__PUBLIC_KEYS__' >"$FIRSTHOME/.ssh/authorized_keys"
chown "$FIRSTUSER:$FIRSTGROUP" "$FIRSTHOME/.ssh/authorized_keys"
chmod 600 "$FIRSTHOME/.ssh/authorized_keys"
install -m 755 -d /etc/ssh/sshd_config.d
printf '%s\n' 'PasswordAuthentication no' > /etc/ssh/sshd_config.d/99-pal-key-only.conf
touch "$BOOTDIR/ssh"
ip link set eth0 up || true
systemctl enable ssh
systemctl enable avahi-daemon || true
hostnamectl set-hostname Melba || true
printf '%s\n' "PAL_SSH_KEY_INSTALLED user=$FIRSTUSER keys=__KEY_COUNT__"
ip -brief address || true
sed -i 's| systemd.run=.*||g' "$BOOTDIR/cmdline.txt"
rm -f "$BOOTDIR/firstrun.sh"
sync
exit 0
'@
$script = $scriptTemplate.Replace('__PUBLIC_KEYS__', $publicKeyLines).Replace('__KEY_COUNT__', [string]$publicKeys.Count).Replace("`r`n", "`n")
if (-not $script.EndsWith("`n")) {
    $script += "`n"
}

$cmdline = (Get-Content -LiteralPath $cmdlinePath -Raw).Trim()
$cmdline = ($cmdline -replace '\s*systemd\.run=[^ ]+', '' -replace '\s*systemd\.run_success_action=[^ ]+', '' -replace '\s*systemd\.unit=[^ ]+', '').Trim()
$cmdline += ' systemd.run=/boot/firmware/firstrun.sh systemd.run_success_action=reboot systemd.unit=kernel-command-line.target'

$utf8NoBom = New-Object Text.UTF8Encoding($false)
[IO.File]::WriteAllText($scriptPath, $script.Replace("`r`n", "`n"), $utf8NoBom)
[IO.File]::WriteAllText($cmdlinePath, $cmdline + "`n", $utf8NoBom)
[IO.File]::WriteAllText($sshFlagPath, '', $utf8NoBom)

$writtenScript = Get-Content -LiteralPath $scriptPath -Raw
$writtenCmdline = Get-Content -LiteralPath $cmdlinePath -Raw
$allPublicKeysEmbedded = $true
foreach ($publicKey in $publicKeys) {
    if (-not $writtenScript.Contains($publicKey)) {
        $allPublicKeysEmbedded = $false
    }
}
$checks = [ordered]@{
    BootPartition = (Split-Path -Qualifier $scriptPath)
    OneShotScriptPresent = (Test-Path -LiteralPath $scriptPath)
    DedicatedPublicKeyEmbedded = $allPublicKeysEmbedded
    PublicKeyCount = $publicKeys.Count
    SshFlagPresent = (Test-Path -LiteralPath $sshFlagPath)
    CorrectBootPath = $writtenCmdline.Contains('systemd.run=/boot/firmware/firstrun.sh')
    AutomaticRebootEnabled = $writtenCmdline.Contains('systemd.run_success_action=reboot')
    OneShotCleanupIncluded = $writtenScript.Contains('rm -f "$BOOTDIR/firstrun.sh"')
    PasswordLoginDisabled = $writtenScript.Contains('PasswordAuthentication no')
    EthernetBringUpIncluded = $writtenScript.Contains('ip link set eth0 up')
    ConfigurationVerified = $false
}
$checks.ConfigurationVerified = $checks.OneShotScriptPresent -and $checks.DedicatedPublicKeyEmbedded -and $checks.SshFlagPresent -and $checks.CorrectBootPath -and $checks.AutomaticRebootEnabled -and $checks.OneShotCleanupIncluded -and $checks.PasswordLoginDisabled -and $checks.EthernetBringUpIncluded

[pscustomobject]$checks | Format-List
if (-not $checks.ConfigurationVerified) {
    throw 'Melba one-shot SSH key installation verification failed.'
}
