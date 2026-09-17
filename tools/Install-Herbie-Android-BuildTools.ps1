<# Install a portable Android build toolchain on D: for Herbie's phone bridge. #>
[CmdletBinding()]
param([string]$InstallRoot = 'D:\Herbie-Android-Build')

$ErrorActionPreference = 'Stop'
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
if (-not $InstallRoot.StartsWith('D:\', [StringComparison]::OrdinalIgnoreCase)) {
    throw "InstallRoot must remain on D:; got $InstallRoot"
}

$Downloads = Join-Path $InstallRoot 'downloads'
$JdkRoot = Join-Path $InstallRoot 'jdk-17'
$SdkRoot = Join-Path $InstallRoot 'android-sdk'
$CommandTools = Join-Path $SdkRoot 'cmdline-tools\latest'
New-Item -ItemType Directory -Path $Downloads, $JdkRoot, $SdkRoot -Force | Out-Null

$JdkZip = Join-Path $Downloads 'microsoft-jdk-17-windows-x64.zip'
$JdkHash = Join-Path $Downloads 'microsoft-jdk-17-windows-x64.zip.sha256sum.txt'
$ToolsZip = Join-Path $Downloads 'android-commandlinetools-win.zip'

if (-not (Test-Path -LiteralPath $JdkZip)) {
    Invoke-WebRequest -Uri 'https://aka.ms/download-jdk/microsoft-jdk-17.0.20.1-windows-x64.zip' -OutFile $JdkZip
}
Invoke-WebRequest -Uri 'https://aka.ms/download-jdk/microsoft-jdk-17.0.20.1-windows-x64.zip.sha256sum.txt' -OutFile $JdkHash
$Expected = ([regex]::Match((Get-Content -LiteralPath $JdkHash -Raw), '[A-Fa-f0-9]{64}')).Value.ToUpperInvariant()
$Actual = (Get-FileHash -LiteralPath $JdkZip -Algorithm SHA256).Hash.ToUpperInvariant()
if (-not $Expected -or $Actual -ne $Expected) { throw 'Microsoft OpenJDK checksum verification failed.' }

if (-not (Get-ChildItem -LiteralPath $JdkRoot -Filter java.exe -Recurse -ErrorAction SilentlyContinue)) {
    Expand-Archive -LiteralPath $JdkZip -DestinationPath $JdkRoot -Force
}
$JavaExe = Get-ChildItem -LiteralPath $JdkRoot -Filter java.exe -Recurse |
    Where-Object { $_.FullName -match '\\bin\\java\.exe$' } | Select-Object -First 1
if (-not $JavaExe) { throw 'Portable Java was not extracted correctly.' }
$env:JAVA_HOME = Split-Path (Split-Path $JavaExe.FullName -Parent) -Parent

if (-not (Test-Path -LiteralPath (Join-Path $CommandTools 'bin\sdkmanager.bat'))) {
    Invoke-WebRequest -Uri 'https://dl.google.com/android/repository/commandlinetools-win-15859902_latest.zip' -OutFile $ToolsZip
    $Extracted = Join-Path $InstallRoot 'command-tools-extracted'
    New-Item -ItemType Directory -Path $Extracted -Force | Out-Null
    Expand-Archive -LiteralPath $ToolsZip -DestinationPath $Extracted -Force
    New-Item -ItemType Directory -Path $CommandTools -Force | Out-Null
    Copy-Item -Path (Join-Path $Extracted 'cmdline-tools\*') -Destination $CommandTools -Recurse -Force
}

$SdkManager = Join-Path $CommandTools 'bin\sdkmanager.bat'
if (-not (Test-Path -LiteralPath $SdkManager)) { throw 'sdkmanager was not installed.' }

# The caller's approval to run this script includes acceptance of the Android
# SDK license presented by sdkmanager. Keep the toolchain portable on D:.
$answers = (1..30 | ForEach-Object { 'y' }) -join "`r`n"
$answers | & $SdkManager --sdk_root=$SdkRoot --licenses | Out-Host
& $SdkManager --sdk_root=$SdkRoot `
    'platform-tools' `
    'platforms;android-36' `
    'build-tools;36.0.0' `
    'cmake;3.22.1' `
    'ndk;28.2.13676358'
if ($LASTEXITCODE -ne 0) { throw "sdkmanager failed with exit code $LASTEXITCODE" }

Write-Host "Portable Java: $env:JAVA_HOME" -ForegroundColor Green
Write-Host "Portable Android SDK: $SdkRoot" -ForegroundColor Green
