[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$sshKeygenPath = 'C:\Windows\System32\OpenSSH\ssh-keygen.exe'
$sshDirectory = 'C:\Users\Phyllis\.ssh'
$privateKeyPath = Join-Path $sshDirectory 'pal_melba_ed25519'
$publicKeyPath = $privateKeyPath + '.pub'
$backupUserData = 'C:\Users\Phyllis\Desktop\Drive\Pal\recovery\melba-ssh-before-repair-20260905\user-data'
$templateBackup = 'C:\Users\Phyllis\Desktop\Drive\Pal\recovery\melba-clean-boot-templates-20260905'
$instanceId = 'pal-melba-clean-20260905'

if (-not (Test-Path -LiteralPath $sshKeygenPath)) {
    throw 'Windows OpenSSH key generator is not installed.'
}

New-Item -ItemType Directory -Path $sshDirectory -Force | Out-Null
if (-not (Test-Path -LiteralPath $privateKeyPath)) {
    & $sshKeygenPath -q -t ed25519 -f $privateKeyPath -N '""' -C 'pal-melba'
    if ($LASTEXITCODE -ne 0) {
        throw "ssh-keygen failed with exit code $LASTEXITCODE"
    }
}

$publicKey = (Get-Content -LiteralPath $publicKeyPath -Raw).Trim()
if ($publicKey -notmatch '^ssh-ed25519\s+') {
    throw 'Generated Melba public key is invalid.'
}

$passwordLine = Get-Content -LiteralPath $backupUserData |
    Where-Object { $_ -match '^\s+passwd:' } |
    Select-Object -First 1
if (-not $passwordLine) {
    throw 'Existing Melba password hash was not found.'
}
$passwordHash = (($passwordLine -replace '^\s+passwd:\s*','').Trim()).Trim('"')
if ($passwordHash -notmatch '^\$') {
    throw 'Existing Melba password hash has an unexpected format.'
}

New-Item -ItemType Directory -Path $templateBackup -Force | Out-Null
Copy-Item -LiteralPath @(
    'F:\user-data'
    'F:\meta-data'
    'F:\network-config'
    'F:\cmdline.txt'
) -Destination $templateBackup -Force

$userDataTemplate = @'
#cloud-config
manage_resolv_conf: false

hostname: Melba
manage_etc_hosts: true
packages:
- avahi-daemon
apt:
  preserve_sources_list: true
  conf: |
    Acquire {
      Check-Date "false";
    };
timezone: America/New_York
keyboard:
  model: pc105
  layout: "us"
user:
  name: jfreakingr
  shell: /bin/bash
  lock_passwd: false
  passwd: "__PASSWORD_HASH__"
  ssh_authorized_keys:
    - "__PUBLIC_KEY__"
  sudo: null
ssh_pwauth: false

runcmd:
  - [ systemctl, enable, --now, ssh ]
'@

$userData = $userDataTemplate.Replace('__PASSWORD_HASH__',$passwordHash.Replace('"','\"'))
$userData = $userData.Replace('__PUBLIC_KEY__',$publicKey.Replace('"','\"'))

[System.IO.File]::WriteAllText('F:\user-data',$userData,[System.Text.UTF8Encoding]::new($false))
[System.IO.File]::WriteAllText('F:\meta-data',"instance-id: $instanceId`n",[System.Text.UTF8Encoding]::new($false))
[System.IO.File]::WriteAllText('F:\userconf.txt',"jfreakingr:$passwordHash`n",[System.Text.UTF8Encoding]::new($false))
New-Item -Path 'F:\ssh' -ItemType File -Force | Out-Null

$commandLine = ([System.IO.File]::ReadAllText('F:\cmdline.txt')).Trim()
if ($commandLine -notmatch 'ds=nocloud') {
    $commandLine += " ds=nocloud;i=$instanceId cfg80211.ieee80211_regdom=US"
}
[System.IO.File]::WriteAllText('F:\cmdline.txt',"$commandLine`n",[System.Text.UTF8Encoding]::new($false))

if ((Get-Item -LiteralPath 'F:\ssh').Length -ne 0) {
    throw 'SSH marker is not empty.'
}
if ((Get-Content -LiteralPath 'F:\user-data' -Raw) -notmatch 'ssh_pwauth: false') {
    throw 'Key-only SSH setting was not written.'
}
if ((Get-Content -LiteralPath 'F:\cmdline.txt' -Raw) -notmatch [regex]::Escape("ds=nocloud;i=$instanceId")) {
    throw 'Cloud-init boot selector was not written.'
}

Write-Output 'BOOT_CONFIG_WRITTEN=True'
Write-Output 'SSH_PASSWORD_AUTH=False'
Write-Output "INSTANCE_ID=$instanceId"
& $sshKeygenPath -lf $publicKeyPath
Write-Output "TEMPLATE_BACKUP=$templateBackup"
