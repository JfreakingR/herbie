<# Copy Herbie's face server and face onto the Galaxy over Wi-Fi, check they
   arrived, and open the phone's screen on this PC. Afterwards, in Termux:
     sh /sdcard/Download/herbie-desk/desk/phone/start_face_on_phone.sh #>
[CmdletBinding()]
param([string]$Phone = '192.168.1.185:5555')

$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$Tools = Join-Path $PSScriptRoot 'scrcpy-win64-v4.1\scrcpy-win64-v4.1'
$Adb = Join-Path $Tools 'adb.exe'
$Target = '/sdcard/Download/herbie-desk'

if (-not (Test-Path -LiteralPath (Join-Path $Root 'desk\phone\start_face_on_phone.sh'))) {
    throw "This copy of Herbie is out of date. Run: git pull origin claude/adoring-maxwell-bvtuh9"
}
if (-not (Test-Path -LiteralPath $Adb)) { throw "adb is missing: $Adb" }

Write-Host "Connecting to the Galaxy at $Phone ..."
& $Adb connect $Phone | Out-Null
$devices = (& $Adb devices) -join "`n"
if ($devices -notmatch [regex]::Escape($Phone) + '\s+device') {
    throw "The Galaxy is not reachable over Wi-Fi at $Phone. Plug it into this PC and run scrcpy with --tcpip once."
}

Write-Host "Copying Herbie's face to the phone ..."
# Start clean and name each destination exactly: "adb push dir existing/" can
# drop the folder's contents straight into existing/ instead of existing/dir.
& $Adb -s $Phone shell "rm -rf $Target && mkdir -p $Target/pi_bridge" | Out-Null
& $Adb -s $Phone push (Join-Path $Root 'desk') "$Target/desk" | Out-Null
& $Adb -s $Phone push (Join-Path $Root 'pi_bridge\face') "$Target/pi_bridge/face" | Out-Null

$check = & $Adb -s $Phone shell "ls $Target/desk/phone/start_face_on_phone.sh $Target/pi_bridge/face/spirit.html 2>&1"
if (($check -join ' ') -match 'No such file') { throw "The copy did not arrive: $check" }

Write-Host ''
Write-Host 'Done. Herbie''s face is on the phone.' -ForegroundColor Green
Write-Host 'In the phone window that opens, open Termux and type:'
Write-Host '  sh /sdcard/Download/herbie-desk/desk/phone/start_face_on_phone.sh' -ForegroundColor Cyan
Start-Process -FilePath (Join-Path $Tools 'scrcpy.exe') -ArgumentList @('-s', $Phone, '--no-audio')
