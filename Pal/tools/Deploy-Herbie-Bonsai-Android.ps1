param(
    [string]$ModelPath = "C:\Users\Phyllis\Bonsai-27B-android\Bonsai-27B-Q1_0.gguf",
    [string]$ApkPath = "$PSScriptRoot\..\android_bonsai_reference\release\BonsaiLocal-debug.apk",
    [string]$AdbPath = "$PSScriptRoot\..\.tools\platform-tools\adb.exe",
    [string]$Serial = "R5CR11QCHPY"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$expectedModelSha256 = "17EF842E47450CAEB8EAA3EBFBBAB5D2F2278B62B79BE107985FB69A2F819AA0"
$expectedApkSha256 = "BDAF2D9EE7EE1BBB2A424242678D75AC35F2B770973E3F4C9E58639CE8F93E5C"
$packageName = "com.prismml.bonsailocal"
$activityName = "$packageName/.MainActivity"
$remoteDirectory = "/sdcard/Android/data/$packageName/files/models"
$remoteModel = "$remoteDirectory/Bonsai-27B-Q1_0.gguf"

function Assert-FileHash {
    param(
        [Parameter(Mandatory)] [string]$Path,
        [Parameter(Mandatory)] [string]$Expected
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Required file not found: $Path"
    }
    $actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
    if ($actual -ne $Expected) {
        throw "SHA-256 mismatch for $Path. Expected $Expected; got $actual"
    }
}

if (-not (Test-Path -LiteralPath $AdbPath -PathType Leaf)) {
    throw "ADB not found: $AdbPath"
}

Assert-FileHash -Path $ApkPath -Expected $expectedApkSha256
Assert-FileHash -Path $ModelPath -Expected $expectedModelSha256

$deviceState = (& $AdbPath -s $Serial get-state 2>$null).Trim()
if ($deviceState -ne "device") {
    throw "Authorized Galaxy $Serial is not connected."
}

$phoneModel = (& $AdbPath -s $Serial shell getprop ro.product.model).Trim()
if ($phoneModel -ne "SM-G998U") {
    throw "Refusing deployment: expected SM-G998U, found $phoneModel."
}

& $AdbPath -s $Serial install -r $ApkPath
if ($LASTEXITCODE -ne 0) { throw "APK installation failed." }

# First launch creates Android's app-specific external model directory.
& $AdbPath -s $Serial shell am start -W -n $activityName | Out-Host
if ($LASTEXITCODE -ne 0) { throw "Bonsai Local did not launch." }
& $AdbPath -s $Serial shell am force-stop $packageName

& $AdbPath -s $Serial push $ModelPath $remoteModel
if ($LASTEXITCODE -ne 0) { throw "Model transfer failed." }

$localSize = (Get-Item -LiteralPath $ModelPath).Length
$remoteSize = [long]((& $AdbPath -s $Serial shell stat -c %s $remoteModel).Trim())
if ($remoteSize -ne $localSize) {
    throw "Transferred model size mismatch. Local $localSize; phone $remoteSize."
}

& $AdbPath -s $Serial shell am start -W -n $activityName | Out-Host
if ($LASTEXITCODE -ne 0) { throw "Bonsai Local did not launch with the model." }

Write-Host "Bonsai Q1_0 is installed locally on the Galaxy."
Write-Host "Model: $remoteModel"
Write-Host "Motor authority was not changed."
