<#
.SYNOPSIS
    Make the reboot stand-in restart VAVA's factory app instead of doing nothing.

.DESCRIPTION
    Stop-Herbie-Cloud-Reboots.ps1 replaced /system/bin/reboot with a no-op. That
    stopped the robot rebooting, but VAVA's Reboot.reboot() does several things
    BEFORE it runs the command: it marks the app as "rebooting", mutes the
    volume, tells the wheel chip the host is disconnected, flickers the power
    light, and starts ignoring serial data. With the reboot never happening, the
    app stayed stuck in that state.

    This version kills com.sego.toy.ctl instead. Its daemon (com.sego.toy.daem)
    relaunches it within seconds, with the "rebooting" state gone, while the
    robot itself stays up. Restarts are rate-limited to one per 60 seconds.

    Requires Stop-Herbie-Cloud-Reboots.ps1 to have been run first (the original
    must already be saved as /system/bin/reboot.sego_original). Undo everything
    with Restore-Herbie-Cloud-Reboots.ps1.
#>
$ErrorActionPreference = 'Stop'

$Adb = 'C:\Users\Phyllis\Desktop\Drive\Pal\tools\scrcpy-win64-v4.1\scrcpy-win64-v4.1\adb.exe'
$Serial = '0123456789ABCDEF'

function Herbie([string]$cmd) {
    return ((& $Adb -s $Serial shell $cmd) -join "`n")
}

if (((& $Adb devices) -join "`n") -notmatch "$Serial\s+device") {
    throw "Herbie is not connected over USB. Plug his USB cable in and run this again."
}
if ((Herbie 'ls /system/bin/reboot.sego_original 2>/dev/null') -notmatch 'reboot.sego_original') {
    throw "The original reboot program isn't saved on Herbie yet. Run Stop-Herbie-Cloud-Reboots.ps1 first."
}

# Single-quoted here-string: PowerShell must not touch the $ signs.
# Herbie's toolbox has no cut/head/tr, so uptime is parsed with shell expansion.
$stub = @'
#!/system/bin/sh
# Herbie: VAVA's app "reboots" whenever its dead cloud is unreachable. Rebooting
# the robot is pointless, and a no-op left the app stuck in its pre-reboot state
# (muted, "disconnected", ignoring serial data). Instead, restart only the app.
# Original program: /system/bin/reboot.sego_original
LOG=/sdcard/herbie_reboot_blocked.log
STAMP=/sdcard/.herbie_app_restart
read UP REST < /proc/uptime
NOW=${UP%%.*}
LAST=0
[ -f $STAMP ] && read LAST < $STAMP
if [ $((NOW - LAST)) -lt 60 ]; then
    echo "$(date) reboot args='$*' parent=$PPID -> skipped (app restarted ${LAST}s uptime)" >> $LOG
    exit 0
fi
echo $NOW > $STAMP
echo "$(date) reboot args='$*' parent=$PPID -> restarting factory app" >> $LOG
( sleep 3
  for p in $(ps | grep com.sego.toy.ctl | while read u pid rest; do echo $pid; done); do
      kill -9 $p
  done ) > /dev/null 2>&1 &
exit 0
'@
$stub = $stub -replace "`r`n", "`n"
if (-not $stub.EndsWith("`n")) { $stub += "`n" }

$local = Join-Path $env:TEMP 'herbie_reboot_standin_v2.sh'
[System.IO.File]::WriteAllText($local, $stub)
& $Adb -s $Serial push $local /sdcard/herbie_reboot_standin_v2.sh | Out-Null

$before = Herbie 'ps | grep com.sego.toy.ctl'
Write-Host "Factory app before: $before"

$swap = 'mount -o remount,rw /system && ' +
        'cat /sdcard/herbie_reboot_standin_v2.sh > /system/bin/reboot && ' +
        'chown root:shell /system/bin/reboot && chmod 755 /system/bin/reboot; ' +
        'mount -o remount,ro /system; ' +
        'ls -l /system/bin/reboot /system/bin/reboot.sego_original'
Write-Host (Herbie $swap)

if ((Herbie 'cat /system/bin/reboot') -notmatch 'restarting factory app') {
    throw 'New stand-in did not install. The previous stand-in and the saved original are unchanged.'
}

# Self-test: this should restart the factory app and NOT the robot.
$upBefore = Herbie 'cat /proc/uptime'
# The trailing sleep keeps the adb shell open; closing it would kill the
# stand-in's background restart before it fires.
Herbie 'rm -f /sdcard/.herbie_app_restart; /system/bin/reboot selftest-v2; sleep 6' | Out-Null
Write-Host 'Self-test sent. Waiting 15 seconds for the app to come back...'
Start-Sleep -Seconds 15

$after = Herbie 'ps | grep com.sego.toy.ctl'
$upAfter = Herbie 'cat /proc/uptime'
Write-Host "Factory app after:  $after"
Write-Host "Uptime before/after: $($upBefore.Split(' ')[0])s -> $($upAfter.Split(' ')[0])s"
Write-Host ''
if ([double]$upAfter.Split(' ')[0] -lt [double]$upBefore.Split(' ')[0]) {
    Write-Host 'WARNING: Herbie restarted fully. Tell Claude.'
} elseif ($after -and $after -ne $before) {
    Write-Host 'Done. The factory app restarted and Herbie stayed up.'
} else {
    Write-Host 'Installed, but the factory app did not visibly restart. Tell Claude what this printed.'
}
