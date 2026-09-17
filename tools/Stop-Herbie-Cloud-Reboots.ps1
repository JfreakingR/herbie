<#
.SYNOPSIS
    Stop VAVA's factory app from rebooting Herbie every few minutes.

.DESCRIPTION
    VAVA's cloud servers no longer exist. The factory app (com.sego.toy.ctl)
    treats the permanent "Offline" state as a glitch: it kills its camera
    helper, then runs the shell command `reboot`. It also has a once-a-day
    auto-reboot. Both call /system/bin/reboot.

    This replaces that one program with a stand-in that only appends a line
    to /sdcard/herbie_reboot_blocked.log. Lights, sensors, movement and the
    serial link are untouched. Herbie can still be restarted with his power
    button, or from the computer with `adb reboot` (which does not use this
    program).

    The original is kept on Herbie as /system/bin/reboot.sego_original and
    copied to %USERPROFILE%\.herbie\backups. Undo with
    Restore-Herbie-Cloud-Reboots.ps1.
#>
$ErrorActionPreference = 'Stop'

$Adb = 'C:\Users\Phyllis\Desktop\Drive\Pal\tools\scrcpy-win64-v4.1\scrcpy-win64-v4.1\adb.exe'
$Serial = '0123456789ABCDEF'
$BackupDir = Join-Path $env:USERPROFILE '.herbie\backups'
$Backup = Join-Path $BackupDir 'vava-system-bin-reboot.original'

function Herbie([string]$cmd) {
    $out = & $Adb -s $Serial shell $cmd
    return ($out -join "`n")
}

if (((& $Adb devices) -join "`n") -notmatch "$Serial\s+device") {
    throw "Herbie is not connected. He may be mid-restart - wait 30 seconds and run this again."
}

$existing = Herbie 'ls /system/bin/reboot.sego_original 2>/dev/null'
if ($existing -match 'reboot.sego_original') {
    Write-Host 'Already done - the stand-in is in place. Nothing changed.'
    exit 0
}

# 1. Back up the original to this computer and check it arrived intact.
New-Item -ItemType Directory -Force $BackupDir | Out-Null
& $Adb -s $Serial pull /system/bin/reboot $Backup | Out-Null
$size = (Get-Item $Backup).Length
if ($size -lt 1000) { throw "Backup looks wrong ($size bytes). Stopping before changing Herbie." }
Write-Host "Backed up original reboot program ($size bytes) to $Backup"

# 2. The stand-in. LF line endings - Android's shell rejects CRLF.
$stub = "#!/system/bin/sh`n" +
        "# Herbie: VAVA's app reboots the robot when its dead cloud server is unreachable.`n" +
        "# This stand-in logs the attempt and does nothing. Original: /system/bin/reboot.sego_original`n" +
        "echo `"`$(date) blocked reboot args='`$*' parent=`$PPID`" >> /sdcard/herbie_reboot_blocked.log`n" +
        "exit 0`n"
$local = Join-Path $env:TEMP 'herbie_reboot_stub.sh'
[System.IO.File]::WriteAllText($local, $stub)
& $Adb -s $Serial push $local /sdcard/herbie_reboot_stub.sh | Out-Null

# 3. Swap it in. Rename first so the original is never lost, then copy the stub.
$swap = 'mount -o remount,rw /system && ' +
        'mv /system/bin/reboot /system/bin/reboot.sego_original && ' +
        'cat /sdcard/herbie_reboot_stub.sh > /system/bin/reboot && ' +
        'chown root:shell /system/bin/reboot && chmod 755 /system/bin/reboot; ' +
        'mount -o remount,ro /system; ' +
        'rm -f /sdcard/herbie_reboot_stub.sh; ' +
        'ls -l /system/bin/reboot /system/bin/reboot.sego_original'
Write-Host (Herbie $swap)

# 4. Verify without rebooting: the stand-in must be the small script, and
#    calling it must only write to the log.
$check = Herbie 'cat /system/bin/reboot'
if ($check -notmatch 'blocked reboot') {
    Write-Host 'Swap did not take. Putting the original back.'
    Write-Host (Herbie 'mount -o remount,rw /system; [ -f /system/bin/reboot.sego_original ] && mv -f /system/bin/reboot.sego_original /system/bin/reboot; mount -o remount,ro /system; ls -l /system/bin/reboot')
    throw 'Stand-in not installed. Herbie is unchanged.'
}
Herbie '/system/bin/reboot selftest' | Out-Null
Write-Host (Herbie 'cat /sdcard/herbie_reboot_blocked.log')
Write-Host ''
Write-Host 'Done. Herbie did not restart during that self-test, so the stand-in works.'
Write-Host 'He will keep trying to reboot every few minutes; each attempt now just adds a line to'
Write-Host '/sdcard/herbie_reboot_blocked.log. Undo with Restore-Herbie-Cloud-Reboots.ps1.'
