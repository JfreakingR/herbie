<#
.SYNOPSIS
Rebuild the Herbie Brain Android app from android_brain\overlay and install it.

Uses what is already on this PC: the portable JDK/SDK/NDK that
Install-Herbie-Android-BuildTools.ps1 put on D:\Herbie-Android-Build, and the
upstream project checkout in android_bonsai_reference\ (git-ignored).

Steps: copy the overlay over the checkout, build an ARM64 debug APK, save it as
android_brain\release\HerbieBrain-debug.apk with a fresh SHA256.txt, and with
-Install put it on the Galaxy (install -r keeps the app's settings and tokens),
then open it so its service starts with the microphone.

It never uninstalls. If Android refuses the update because this build is
signed with a different key, it stops and says so.
#>
[CmdletBinding()]
param(
    [string]$BuildRoot = 'D:\Herbie-Android-Build',
    [string]$Project,
    [string]$DeviceSerial = 'R5CR11QCHPY',
    [switch]$Install
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
if (-not $Project) { $Project = Join-Path $Root 'android_bonsai_reference' }
$Overlay = Join-Path $Root 'android_brain\overlay'
$Release = Join-Path $Root 'android_brain\release'
$Adb = Join-Path $Root '.tools\platform-tools\adb.exe'
$Package = 'com.prismml.herbiebrain'

if (-not (Test-Path -LiteralPath (Join-Path $Project 'app\src\main'))) {
    throw "No Android project at $Project. It is the upstream checkout the last build used (see android_brain\README.md)."
}
# The project's own wrapper if it has one; otherwise a Gradle unpacked with the
# portable toolchain (this checkout was built that way, without gradlew.bat).
$Gradle = Join-Path $Project 'gradlew.bat'
if (-not (Test-Path -LiteralPath $Gradle)) {
    $found = Get-ChildItem -LiteralPath $BuildRoot -Filter gradle.bat -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match '\\bin\\gradle\.bat$' } | Select-Object -First 1
    if (-not $found) {
        $found = Get-ChildItem -LiteralPath "$env:USERPROFILE\.gradle\wrapper\dists" -Filter gradle.bat -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match '\\bin\\gradle\.bat$' } | Sort-Object FullName -Descending | Select-Object -First 1
    }
    if (-not $found) { throw "No gradlew.bat in $Project and no Gradle under $BuildRoot or ~\.gradle. Tell Claude." }
    $Gradle = $found.FullName
}
Write-Host "Using Gradle: $Gradle"
$java = Get-ChildItem -LiteralPath (Join-Path $BuildRoot 'jdk-17') -Filter java.exe -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match '\\bin\\java\.exe$' } | Select-Object -First 1
if (-not $java) { throw "No JDK under $BuildRoot. Run tools\Install-Herbie-Android-BuildTools.ps1 first." }
$env:JAVA_HOME = Split-Path (Split-Path $java.FullName -Parent) -Parent
$env:ANDROID_HOME = Join-Path $BuildRoot 'android-sdk'
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME
# The earlier build kept Gradle's downloads and caches here; without this Gradle
# would fetch everything again into the user profile on C:.
$GradleHome = Join-Path $BuildRoot 'gradle-home'
if (Test-Path -LiteralPath $GradleHome) { $env:GRADLE_USER_HOME = $GradleHome }
if (-not (Test-Path -LiteralPath $env:ANDROID_HOME)) { throw "No Android SDK at $env:ANDROID_HOME." }

Write-Host "Copying Herbie's overlay into $Project ..." -ForegroundColor Cyan
Copy-Item -Path (Join-Path $Overlay '*') -Destination $Project -Recurse -Force

Write-Host 'Building (several minutes the first time) ...' -ForegroundColor Cyan
Push-Location $Project
try {
    # --no-daemon and --no-watch-fs: both stalled the earlier build on this PC
    # (Gradle probed an empty removable drive and hung). The flag, unlike a -D
    # property, also reaches the single-use daemon Gradle forks.
    & $Gradle ':app:assembleDebug' --no-daemon --no-watch-fs --console=plain
    if ($LASTEXITCODE -ne 0) { throw "Build failed (exit $LASTEXITCODE). The first error above is the one to fix." }
} finally {
    Pop-Location
}

$apk = Get-ChildItem -LiteralPath (Join-Path $Project 'app\build\outputs\apk\debug') -Filter *.apk |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $apk) { throw 'Build finished but no APK was found.' }
$target = Join-Path $Release 'HerbieBrain-debug.apk'
Copy-Item -LiteralPath $apk.FullName -Destination $target -Force
$hash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
[System.IO.File]::WriteAllText((Join-Path $Release 'SHA256.txt'), "$hash  HerbieBrain-debug.apk`n")
Write-Host "Built $target" -ForegroundColor Green
Write-Host "SHA256 $hash"

if (-not $Install) {
    Write-Host 'Not installed. Re-run with -Install to put it on the phone.'
    exit 0
}

$result = (& $Adb -s $DeviceSerial install -r $target 2>&1) -join "`n"
Write-Host $result
if ($result -match 'INSTALL_FAILED_UPDATE_INCOMPATIBLE|signatures do not match') {
    Write-Host ''
    Write-Host 'Android refused: this build is signed with a different key than the app on the phone.' -ForegroundColor Red
    Write-Host 'Nothing was changed on the phone. Do NOT uninstall yet - that wipes its settings. Tell Claude.' -ForegroundColor Yellow
    exit 1
}
if ($result -notmatch 'Success') { throw 'Install did not report Success.' }

# Open it so the service (re)starts from the foreground, with the microphone.
& $Adb -s $DeviceSerial shell am force-stop $Package | Out-Null
& $Adb -s $DeviceSerial shell monkey -p $Package -c android.intent.category.LAUNCHER 1 | Out-Null
Write-Host ''
Write-Host 'Installed and opened. On the phone, turn on:' -ForegroundColor Green
Write-Host '  Settings > Apps > Herbie > Appear on top  (so he can hear straight after a restart)'
