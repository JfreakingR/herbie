<#
.SYNOPSIS
    Undo Stop-Herbie-Cloud-Reboots.ps1: put VAVA's original reboot program back.
#>
$ErrorActionPreference = 'Stop'

$Adb = 'C:\Users\Phyllis\Desktop\Drive\Pal\tools\scrcpy-win64-v4.1\scrcpy-win64-v4.1\adb.exe'
$Serial = '0123456789ABCDEF'

if (((& $Adb devices) -join "`n") -notmatch "$Serial\s+device") {
    throw "Herbie is not connected."
}

$restore = 'if [ -f /system/bin/reboot.sego_original ]; then ' +
           'mount -o remount,rw /system && mv -f /system/bin/reboot.sego_original /system/bin/reboot; ' +
           'mount -o remount,ro /system; echo restored; else echo "nothing to restore"; fi; ' +
           'ls -l /system/bin/reboot'
Write-Host ((& $Adb -s $Serial shell $restore) -join "`n")
Write-Host 'VAVA''s automatic reboots are active again.'
