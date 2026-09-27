<#
.SYNOPSIS
Read-only check of why Herbie is not hearing or not answering out loud.

Say "Herbie, hello" to him first, then run this. It changes nothing on the
phone. It looks at the Herbie Brain app (package com.prismml.herbiebrain,
shown on the phone as "Bonsai"): microphone permission, whether its service
actually holds the microphone, its own log (ears, voice, service), media
volume and notifications, and prints what it finds in plain words.
#>
[CmdletBinding()]
param(
    [string]$DeviceSerial = 'R5CR11QCHPY',
    [string]$AdbPath
)

$ErrorActionPreference = 'Continue'
$Package = 'com.prismml.herbiebrain'

if (-not $AdbPath) {
    $AdbPath = Join-Path (Split-Path $PSScriptRoot -Parent) '.tools\platform-tools\adb.exe'
    if (-not (Test-Path -LiteralPath $AdbPath)) {
        $command = Get-Command adb.exe -ErrorAction SilentlyContinue
        if ($command) { $AdbPath = $command.Source } else { throw 'adb.exe not found.' }
    }
}
function Shell([string]$Command) {
    return ((& $AdbPath -s $DeviceSerial shell $Command 2>$null) -join "`n")
}
$script:Problems = 0
function Ok([string]$Text) { Write-Host "  OK       $Text" -ForegroundColor Green }
function Problem([string]$Text, [string]$Fix) {
    $script:Problems++
    Write-Host "  PROBLEM  $Text" -ForegroundColor Red
    Write-Host "           fix: $Fix" -ForegroundColor Yellow
}

if (((& $AdbPath devices) -join "`n") -notmatch ([regex]::Escape($DeviceSerial) + '\s+device')) {
    Write-Host "Galaxy $DeviceSerial is not attached over USB ADB." -ForegroundColor Red
    exit 1
}

$running = (Shell "pidof $Package").Trim()
if ($running) { Ok 'Herbie Brain app is running.' }
else { Problem 'Herbie Brain app is not running.' 'Open the Bonsai app that says "Herbie''s private local model service".' }

$pkg = Shell "dumpsys package $Package"
if ($pkg -match 'android\.permission\.RECORD_AUDIO: granted=true') { Ok 'Microphone permission granted.' }
else { Problem 'The app is not allowed to use the microphone.' 'Settings > Apps > Bonsai (Herbie) > Permissions > Microphone > Allow.' }
if ($pkg -match 'android\.permission\.POST_NOTIFICATIONS: granted=true') { Ok 'Notifications allowed.' }
else { Problem 'Notifications are off for the app.' 'Settings > Apps > Bonsai (Herbie) > Notifications > on. (Not fatal, but hides his status.)' }

# Does the running service actually hold the microphone? Type bit 0x80.
$services = Shell "dumpsys activity services $Package"
if ($services -match '(?:foregroundServiceType|types)=0x([0-9a-fA-F]+)') {
    $types = [Convert]::ToInt64($Matches[1], 16)
    if ($types -band 0x40) { Ok 'His service holds the camera (he can see).' }
    else { Problem 'His service does not hold the camera, so he cannot see.' `
            'adb shell pm grant com.prismml.herbiebrain android.permission.CAMERA, then force stop and open the Herbie app.' }
    if ($types -band 0x80) { Ok 'His service holds the microphone.' }
    else {
        Problem 'His service is running WITHOUT the microphone, so he cannot hear.' `
            'Settings > Apps > Bonsai (Herbie) > Force stop, then open that app. (The rebuilt app fixes this after restarts.)'
    }
} else {
    Write-Host '  ?        Could not read the service type.' -ForegroundColor DarkYellow
}

$volume = Shell 'cmd media_session volume --stream 3 --get'
if ($volume -match 'volume is (\d+) in range \[(\d+)\.\.(\d+)\]') {
    if ([int]$Matches[1] -eq 0) { Problem 'Media volume is 0.' 'Turn the media volume up on the phone.' }
    else { Ok "Media volume $($Matches[1]) of $($Matches[3])." }
}

Write-Host ''
Write-Host 'His own log (most recent last):'
$log = (& $AdbPath -s $DeviceSerial logcat -d -s 'HerbieEars:*' 'HerbieVoice:*' 'HerbieModelService:*' 'HerbieModelBridge:*' 2>$null) |
    Where-Object { $_ -and $_ -notmatch '^-{5}' } | Select-Object -Last 25
if (-not $log) {
    Write-Host '  (nothing logged - his service has not started since the log was cleared)' -ForegroundColor DarkYellow
} else {
    $log | ForEach-Object { Write-Host "  $_" }
    $text = $log -join "`n"
    Write-Host ''
    if ($text -match 'running without ears') { Problem 'He started without ears.' 'Force stop the app and open it again (see above).' }
    if ($text -match 'Brain token missing') { Problem 'His hearing was never linked to his brain on this install.' 'Needs re-provisioning with the brain token - tell Claude.' }
    if ($text -match 'No speech recognizer') { Problem 'The phone has no speech recognizer available.' 'Install/enable the Google app or "Speech Recognition and Synthesis from Google".' }
    if ($text -match 'Brain unavailable') { Problem 'He heard you but could not reach his brain.' 'Run tools\Check-Herbie-Boot.ps1.' }
    if ($text -match 'Heard \(') { Ok 'He is hearing speech (see the Heard lines above).' }
    if ($text -notmatch 'HerbieEars|without ears|Brain token missing') {
        Problem 'No hearing code ran at all - the installed app is probably an old build without ears.' `
            'adb install -r android_brain\release\HerbieBrain-debug.apk, then force stop and open the app.'
    }
    if ($text -match 'Playback failed') { Problem 'He tried to speak and playback failed.' 'Check the speaker / Bluetooth connection.' }
}

Write-Host ''
if ($script:Problems -eq 0) { Write-Host 'No problem found. Paste this output to Claude.' -ForegroundColor Green }
else { Write-Host "$($script:Problems) problem(s) found. Fix the first one and say ""Herbie, hello"" again." -ForegroundColor Yellow }
