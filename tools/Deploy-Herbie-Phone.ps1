<#
.SYNOPSIS
    Stage Herbie phone brain 0.5.0 onto the Galaxy and stop the phone dropping off.

.DESCRIPTION
    Waits for the Galaxy over ADB, applies the settings that keep it awake and
    keep Termux running, then pushes the brain source to the staging directory
    that install_pal_brain.sh reads from.

    It does NOT install by itself: the install script has to run inside Termux,
    because Termux's home lives under /data/data/com.termux which the adb shell
    user cannot write to. The script tries Termux's RunCommandService and falls
    back to printing what to run.

    Nothing here touches motors, the battery, or the VAVA boards.
#>
[CmdletBinding()]
param(
    [string]$DeviceSerial = 'R5CR11QCHPY',
    [int]$WaitSeconds = 120,
    [switch]$SkipKeepAwake
)

$ErrorActionPreference = 'Stop'

$ToolDirectory = Join-Path $PSScriptRoot 'scrcpy-win64-v4.1\scrcpy-win64-v4.1'
$AdbPath = Join-Path $ToolDirectory 'adb.exe'
$SourceDirectory = Join-Path (Split-Path $PSScriptRoot -Parent) 'phone_brain'
$StagingDirectory = '/sdcard/Download/PalBrain'

if (-not (Test-Path -LiteralPath $AdbPath)) {
    Write-Error "ADB is missing from $ToolDirectory"
    exit 1
}
if (-not (Test-Path -LiteralPath $SourceDirectory)) {
    Write-Error "Source directory not found: $SourceDirectory"
    exit 1
}

function Invoke-Adb {
    # No 2>&1 here. Windows PowerShell 5.1 wraps a native command's stderr in
    # ErrorRecords, which turns adb's ordinary progress output ("1 file pushed")
    # into a fatal NativeCommandError under ErrorActionPreference = Stop.
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $AdbPath -s $DeviceSerial @Arguments
    } finally {
        $ErrorActionPreference = $previous
    }
}

# ---------------------------------------------------------------- wait for it
Write-Host "Waiting up to $WaitSeconds s for $DeviceSerial ..." -ForegroundColor Cyan
$deadline = (Get-Date).AddSeconds($WaitSeconds)
$found = $false
while ((Get-Date) -lt $deadline) {
    $devices = (& $AdbPath devices) -join "`n"
    if ($devices -match "$DeviceSerial\s+device") { $found = $true; break }
    if ($devices -match "$DeviceSerial\s+unauthorized") {
        Write-Warning 'Device is UNAUTHORIZED. Accept the USB debugging prompt on the phone.'
    }
    Start-Sleep -Seconds 2
}

if (-not $found) {
    Write-Warning "$DeviceSerial did not appear."
    $pnp = Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue |
        Where-Object { $_.InstanceId -match [regex]::Escape($DeviceSerial) }
    if ($pnp) {
        Write-Warning "Windows sees it as: $($pnp.Status) - $($pnp.ProblemDescription)"
        if ($pnp.Problem -eq 'CM_PROB_FAILED_START') {
            Write-Host ''
            Write-Host 'Code 10 means the USB driver would not start. Unplug and replug,' -ForegroundColor Yellow
            Write-Host 'preferring a USB 2.0 port directly on the machine rather than a hub.' -ForegroundColor Yellow
        }
    } else {
        Write-Warning 'Windows cannot see the phone at all - check the cable and port.'
    }
    exit 1
}
Write-Host "Connected." -ForegroundColor Green

# ------------------------------------------------------------- keep it awake
if (-not $SkipKeepAwake) {
    Write-Host ''
    Write-Host 'Applying keep-awake settings...' -ForegroundColor Cyan

    # 7 = stay awake on AC + USB + wireless charging. Stops Android suspending
    # the device (and the ADB connection with it) while it is plugged in.
    Invoke-Adb shell 'settings put global stay_on_while_plugged_in 7' | Out-Null
    $stayOn = (Invoke-Adb shell 'settings get global stay_on_while_plugged_in').Trim()
    Write-Host "  stay_on_while_plugged_in = $stayOn"

    # Exempt Termux from Doze so the brain is not frozen in the background.
    Invoke-Adb shell 'dumpsys deviceidle whitelist +com.termux' | Out-Null
    $whitelisted = Invoke-Adb shell 'dumpsys deviceidle whitelist' | Select-String 'com.termux'
    if ($whitelisted) {
        Write-Host '  com.termux exempted from Doze'
    } else {
        Write-Host '  WARNING: could not confirm Termux Doze exemption' -ForegroundColor Yellow
    }

    # Keep the screen from sleeping the USB stack. The screen is broken, so this
    # costs nothing visually, but it does keep the phone warmer - unplug when idle.
    Invoke-Adb shell 'settings put system screen_off_timeout 1800000' | Out-Null
    Write-Host '  screen_off_timeout = 30 min'
}

# ------------------------------------------------------------------ push files
Write-Host ''
Write-Host "Staging source to $StagingDirectory ..." -ForegroundColor Cyan
Invoke-Adb shell "mkdir -p $StagingDirectory" | Out-Null

$filesToPush = @(
    'pal_phone_brain.py',
    'herbie_memory.py',
    'herbie_voice.py',
    'herbie_autonomic.py',
    'start_pal_brain.sh',
    'stop_pal_brain.sh',
    'herbie_supervisor.sh',
    'boot_herbie.sh',
    'install_pal_brain.sh',
    'test_herbie_memory.py',
    'test_herbie_rights.py',
    'test_herbie_autonomic.py',
    'test_herbie_voice.py',
    'test_herbie_is_free.py'
)

$pushed = 0
foreach ($file in $filesToPush) {
    $local = Join-Path $SourceDirectory $file
    if (-not (Test-Path -LiteralPath $local)) {
        Write-Warning "  missing locally, skipped: $file"
        continue
    }
    # Termux's bash cannot run a script with CRLF endings: it reads the CR as
    # part of the command and fails with "$'\r': command not found". Editing
    # these from Windows reintroduces that easily, so check before pushing.
    if ($file -like '*.sh') {
        $bytes = [System.IO.File]::ReadAllBytes($local)
        for ($i = 0; $i -lt $bytes.Length; $i++) {
            if ($bytes[$i] -eq 13) {
                Write-Warning "  $file has CRLF endings; converting to LF before push."
                $text = [System.IO.File]::ReadAllText($local) -replace "`r`n", "`n"
                [System.IO.File]::WriteAllText($local, $text)
                break
            }
        }
    }
    $result = Invoke-Adb push $local "$StagingDirectory/$file"
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  pushed $file"
        $pushed++
    } else {
        Write-Warning "  FAILED to push $file : $result"
    }
}
Write-Host "$pushed of $($filesToPush.Count) files staged." -ForegroundColor Green

# --------------------------------------------------- try to run the installer
Write-Host ''
Write-Host 'Attempting to run the installer inside Termux...' -ForegroundColor Cyan

$termuxHome = '/data/data/com.termux/files/home'
$runCommand = Invoke-Adb shell ("am startservice --user 0 " +
    "-n com.termux/com.termux.app.RunCommandService " +
    "-a com.termux.RUN_COMMAND " +
    "--es com.termux.RUN_COMMAND_PATH '/data/data/com.termux/files/usr/bin/bash' " +
    "--esa com.termux.RUN_COMMAND_ARGUMENTS '$StagingDirectory/install_pal_brain.sh' " +
    "--es com.termux.RUN_COMMAND_WORKDIR '$termuxHome' " +
    "--ez com.termux.RUN_COMMAND_BACKGROUND 'true'")

# The refusal is printed on stderr, which Invoke-Adb deliberately does not
# capture, so an empty result means "could not tell", not "it worked".
if (-not $runCommand -or $runCommand -match 'Error|Exception|SecurityException|does not exist') {
    Write-Host ''
    Write-Host 'Could not launch it remotely (this is normal unless Termux has' -ForegroundColor Yellow
    Write-Host 'allow-external-apps=true and the RUN_COMMAND permission granted).' -ForegroundColor Yellow
    Write-Host ''
    Write-Host 'Run this inside Termux instead - via scrcpy if the screen is unusable:' -ForegroundColor White
    Write-Host "  bash $StagingDirectory/install_pal_brain.sh" -ForegroundColor White
} else {
    Write-Host '  RunCommandService may have accepted the request; verifying below.'
    Start-Sleep -Seconds 8
}

# ------------------------------------------------------------------- verify
Write-Host ''
Write-Host 'Checking the service...' -ForegroundColor Cyan
Invoke-Adb forward tcp:18765 tcp:8765 | Out-Null
try {
    $health = Invoke-RestMethod -Uri 'http://127.0.0.1:18765/health' -TimeoutSec 5
    Write-Host "  version: $($health.version)"
    Write-Host "  ready:   $($health.ready)"
    Write-Host "  motor_authority: $($health.motor_authority)   safe_motion_state: $($health.safe_motion_state)"
    # Read the expected version from source rather than hardcoding it, or a
    # stale deploy will cheerfully report itself as a success.
    $versionMatch = Select-String -Path (Join-Path $SourceDirectory 'pal_phone_brain.py') `
        -Pattern 'SERVICE_VERSION' | Select-Object -First 1
    $expected = if ($versionMatch -and $versionMatch.Line -match '"([^"]+)"') {
        $Matches[1]
    } else { '' }
    if ($expected -and $health.version -eq $expected) {
        Write-Host "  $expected is live." -ForegroundColor Green
        Write-Host ''
        Write-Host 'Verify fully with:' -ForegroundColor White
        Write-Host "  powershell -File `"$PSScriptRoot\Test-Pal-Phone-Brain.ps1`"" -ForegroundColor White
    } else {
        Write-Host "  Live is $($health.version); source is $expected - the installer has not run yet." -ForegroundColor Yellow
    }
} catch {
    Write-Host '  No response yet. Run the install command above inside Termux.' -ForegroundColor Yellow
}
