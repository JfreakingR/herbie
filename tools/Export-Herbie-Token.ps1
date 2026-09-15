<#
.SYNOPSIS
    Copy Herbie's API token from the phone to this workstation, once.

.DESCRIPTION
    Termux's home is private to the Termux UID, so `adb shell cat` cannot read
    the token. The only channel between Termux and this machine is shared
    storage, so the token takes a brief trip through /sdcard.

    That trip is the weak point: while the file is on /sdcard, any app holding
    storage permission could read it. This script therefore copies, pulls, and
    deletes the shared copy immediately, and never prints the token.

    The token lands in %USERPROFILE%\.herbie\api-token with inheritance removed
    and access restricted to the current user.

    Re-run this if the token is ever regenerated on the phone.
#>
[CmdletBinding()]
param(
    [string]$DeviceSerial = 'R5CR11QCHPY'
)

$ErrorActionPreference = 'Stop'

$AdbPath = Join-Path $PSScriptRoot 'scrcpy-win64-v4.1\scrcpy-win64-v4.1\adb.exe'
$StagingDirectory = '/sdcard/Download/PalBrain'
$ShuttleFile = "$StagingDirectory/.token-shuttle"
$TokenDirectory = Join-Path $env:USERPROFILE '.herbie'
$TokenFile = Join-Path $TokenDirectory 'api-token'
$HelperName = 'export_token.sh'
$HelperLocal = Join-Path $env:TEMP $HelperName

if (-not (Test-Path -LiteralPath $AdbPath)) {
    Write-Error "ADB is missing: $AdbPath"
    exit 1
}

# -join first: `-notmatch` against an array returns the non-matching
# ELEMENTS, not a boolean, so the header line alone would make this fire.
$attached = (& $AdbPath devices) -join "`n"
if ($attached -notmatch "$DeviceSerial\s+device") {
    Write-Error "Galaxy $DeviceSerial is not attached over ADB."
    exit 1
}

# LF endings matter: Termux's bash will not run a script with CRLF line endings.
$helper = @(
    '#!/data/data/com.termux/files/usr/bin/bash',
    'set -eu',
    'SRC="$HOME/pal-phone-brain/herbie-api-token"',
    'if [ ! -f "$SRC" ]; then echo "NO_TOKEN"; exit 1; fi',
    "cp `"`$SRC`" $ShuttleFile",
    'echo COPIED'
) -join "`n"
[System.IO.File]::WriteAllText($HelperLocal, $helper + "`n")

& $AdbPath -s $DeviceSerial push $HelperLocal "$StagingDirectory/$HelperName" | Out-Null

$focus = & $AdbPath -s $DeviceSerial shell 'dumpsys window | grep mCurrentFocus'
if ($focus -notmatch 'com.termux') {
    Write-Warning 'Termux is not the focused app; bring it to the foreground first.'
    Write-Warning "Or run this inside Termux:  bash $StagingDirectory/$HelperName"
    exit 1
}

Write-Host 'Asking Termux to stage the token...' -ForegroundColor Cyan
& $AdbPath -s $DeviceSerial shell "input text 'bash%s$StagingDirectory/$HelperName'"
Start-Sleep -Milliseconds 500
& $AdbPath -s $DeviceSerial shell 'input keyevent 66'
Start-Sleep -Seconds 6

New-Item -ItemType Directory -Path $TokenDirectory -Force | Out-Null
& $AdbPath -s $DeviceSerial pull $ShuttleFile $TokenFile | Out-Null

# Remove the shared-storage copy straight away, whether or not the pull worked.
& $AdbPath -s $DeviceSerial shell "rm -f $ShuttleFile" | Out-Null
& $AdbPath -s $DeviceSerial shell "rm -f $StagingDirectory/$HelperName" | Out-Null
Remove-Item -LiteralPath $HelperLocal -Force -ErrorAction SilentlyContinue

if (-not (Test-Path -LiteralPath $TokenFile)) {
    Write-Error 'Token was not retrieved. Is the brain installed and started?'
    exit 1
}

$length = (Get-Item -LiteralPath $TokenFile).Length
if ($length -lt 8) {
    Remove-Item -LiteralPath $TokenFile -Force
    Write-Error "Retrieved file was only $length bytes; discarded rather than stored."
    exit 1
}

# Restrict to the current user only.
$acl = Get-Acl -LiteralPath $TokenFile
$acl.SetAccessRuleProtection($true, $false)
$acl.Access | ForEach-Object { [void]$acl.RemoveAccessRule($_) }
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
    "$env:USERDOMAIN\$env:USERNAME", 'FullControl', 'Allow')
$acl.AddAccessRule($rule)
Set-Acl -LiteralPath $TokenFile -AclObject $acl

Write-Host ''
Write-Host "Token stored at $TokenFile ($length bytes), readable only by you." -ForegroundColor Green
Write-Host 'The shared-storage copy has been deleted. The token was never printed.'
Write-Host ''
Write-Host 'Test-Pal-Phone-Brain.ps1 will now pick it up automatically.'
