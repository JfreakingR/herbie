<#
.SYNOPSIS
Read-only check of why Herbie's brain did or did not start after the Galaxy
restarted. Run it a minute or two after the phone reboots.

It changes nothing on the phone. Each line is OK or a PROBLEM with the fix.

Herbie auto-starts through two hooks:
  * Termux:Boot runs ~/.termux/boot/boot_herbie.sh -> herbie_supervisor.sh
    -> pal_phone_brain.py (memory, voice, chat routing, neck queue).
  * The Herbie Brain app's BOOT_COMPLETED receiver starts its foreground
    model service (the offline fallback model, TTS and ears).
Android delivers neither until the phone has been unlocked once after the
restart, and Samsung's battery manager can silently block both.
#>
[CmdletBinding()]
param(
    [string]$DeviceSerial = 'R5CR11QCHPY',
    [string]$AdbPath
)

# Continue, not Stop: Windows PowerShell 5.1 turns any adb stderr line into a
# terminating error under Stop, and this check should report, not abort.
$ErrorActionPreference = 'Continue'

function Resolve-Adb {
    if ($AdbPath) { return $AdbPath }
    $root = Split-Path $PSScriptRoot -Parent
    $candidates = @(
        (Join-Path $root '.tools\platform-tools\adb.exe'),
        (Join-Path $PSScriptRoot 'scrcpy-win64-v4.1\scrcpy-win64-v4.1\adb.exe')
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }
    $command = Get-Command adb.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    throw 'adb.exe not found.'
}

$Adb = Resolve-Adb
$script:Problems = 0

function Shell([string]$Command) {
    $out = & $Adb -s $DeviceSerial shell $Command 2>$null
    return ($out -join "`n")
}
function Ok([string]$Text) { Write-Host "  OK       $Text" -ForegroundColor Green }
function Problem([string]$Text, [string]$Fix) {
    $script:Problems++
    Write-Host "  PROBLEM  $Text" -ForegroundColor Red
    Write-Host "           fix: $Fix" -ForegroundColor Yellow
}

$attached = (& $Adb devices) -join "`n"
if ($attached -notmatch ([regex]::Escape($DeviceSerial) + '\s+device')) {
    Write-Host "Galaxy $DeviceSerial is not attached over USB ADB." -ForegroundColor Red
    exit 1
}

$uptime = [double]((Shell 'cat /proc/uptime').Split(' ')[0])
Write-Host ("Galaxy up for {0:N0} min" -f ($uptime / 60))

# 1. Unlocked since boot? Nothing auto-starts before the first unlock.
$users = Shell 'dumpsys user'
if ($users -match 'RUNNING_LOCKED') {
    Problem 'The phone has not been unlocked since it restarted.' `
        'Unlock it once (or remove the screen lock: Settings > Lock screen > Screen lock type > None/Swipe).'
} else {
    Ok 'Unlocked since restart.'
}

# 2. The apps are installed and not in the "stopped" state. A package that was
#    never opened, or was force-stopped, receives no boot broadcast at all.
$packages = Shell 'pm list packages'
$apps = [ordered]@{
    'com.termux'              = 'Termux'
    'com.termux.boot'         = 'Termux:Boot add-on'
    'com.prismml.herbiebrain' = 'Herbie Brain app'
}
foreach ($pkg in $apps.Keys) {
    $name = $apps[$pkg]
    if ($packages -notmatch ("package:" + [regex]::Escape($pkg) + '(\r?\n|$)')) {
        Problem "$name ($pkg) is not installed." `
            $(if ($pkg -eq 'com.termux.boot') { 'Install Termux:Boot from the same place Termux came from (F-Droid), then open it once.' } else { "Reinstall $name." })
        continue
    }
    $info = Shell "dumpsys package $pkg"
    if ($info -match 'stopped=true') {
        Problem "$name is in Android's stopped state, so it gets no boot signal." `
            "Open $name once from the app drawer (and never Force stop it)."
    } else {
        Ok "$name installed and allowed to receive boot."
    }

    # 3. Samsung / Android background limits.
    $bg = Shell "cmd appops get $pkg RUN_ANY_IN_BACKGROUND"
    $bucket = Shell "am get-standby-bucket $pkg"
    if ($bg -match 'ignore|deny' -or $bucket.Trim() -in @('45', '50')) {
        Problem "$name is restricted in the background (sleeping / restricted app)." `
            "Settings > Apps > $name > Battery > Unrestricted, and remove it from Settings > Battery > Background usage limits > Sleeping / Deep sleeping apps."
    } else {
        Ok "$name is not background-restricted."
    }
}

# 4. What is actually running.
$ps = Shell 'ps -A -o PID,ARGS'
if ($ps -match 'herbie_supervisor') { Ok 'Herbie supervisor is running.' }
else {
    Problem 'Herbie supervisor is not running (Termux:Boot did not start it).' `
        'Check the items above; the boot script must also exist: in Termux run  ls ~/.termux/boot/  (re-run install_pal_brain.sh if boot_herbie.sh is missing).'
}
if ($ps -match 'pal_phone_brain') { Ok 'Herbie phone brain (pal_phone_brain.py) is running.' }
else { Problem 'The phone brain process is not running.' 'See the supervisor line above.' }
if ($ps -match 'com\.prismml\.herbiebrain') { Ok 'Herbie Brain app process is running.' }
else { Problem 'The Herbie Brain app is not running.' 'See its lines above; open the app once after installing.' }

# 5. Does the brain answer?
& $Adb -s $DeviceSerial forward tcp:18765 tcp:8765 | Out-Null
try {
    $health = Invoke-RestMethod -Uri 'http://127.0.0.1:18765/health' -TimeoutSec 5
    Ok "Brain answers: version $($health.version), ready=$($health.ready)."
} catch {
    Problem 'The brain does not answer on port 8765.' 'If it is running, give it a minute; otherwise see above.'
}

Write-Host ''
if ($script:Problems -eq 0) {
    Write-Host 'Everything that starts Herbie at boot looks right.' -ForegroundColor Green
} else {
    Write-Host "$($script:Problems) problem(s). Fix them, restart the phone, unlock it, and run this again." -ForegroundColor Yellow
}
