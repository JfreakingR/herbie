[CmdletBinding()]
param(
    [switch]$CheckOnly
)

$ErrorActionPreference = 'Stop'
$ToolDirectory = Join-Path $PSScriptRoot 'scrcpy-win64-v4.1\scrcpy-win64-v4.1'
$AdbPath = Join-Path $ToolDirectory 'adb.exe'
$ScrcpyPath = Join-Path $ToolDirectory 'scrcpy.exe'
$AdbKeyPath = Join-Path $env:USERPROFILE '.android\adbkey'
$EndpointPath = Join-Path $PSScriptRoot 'pal-phone-endpoint.txt'
$ExpectedSerial = 'R5CR11QCHPY'
$WindowTitle = 'Pal-S21-Ultra'

if (-not (Test-Path -LiteralPath $AdbPath) -or -not (Test-Path -LiteralPath $ScrcpyPath)) {
    Write-Error "Pal phone-control tools are missing from $ToolDirectory"
    exit 1
}

if (-not (Test-Path -LiteralPath $AdbKeyPath)) {
    Write-Error "The saved Android authorization key is missing from $AdbKeyPath"
    exit 1
}

# Pin ADB to one persistent identity. Without the explicit key file, a helper
# launched under a different Windows context can present a new identity and
# force another approval on a phone whose screen cannot be used.
$env:ADB_VENDOR_KEYS = $AdbKeyPath

$DeviceLines = & $AdbPath devices -l
$MatchingLine = $DeviceLines | Where-Object { $_ -match "^$ExpectedSerial\s+" } | Select-Object -First 1
$SelectedSerial = $ExpectedSerial

if (-not $MatchingLine -and (Test-Path -LiteralPath $EndpointPath)) {
    $SavedEndpoint = (Get-Content -LiteralPath $EndpointPath -Raw).Trim()
    if ($SavedEndpoint) {
        & $AdbPath connect $SavedEndpoint | Out-Host
        $DeviceLines = & $AdbPath devices -l
        $MatchingLine = $DeviceLines | Where-Object { $_ -match "^$([regex]::Escape($SavedEndpoint))\s+" } | Select-Object -First 1
        $SelectedSerial = $SavedEndpoint
    }
}

if (-not $MatchingLine) {
    Write-Error 'The Galaxy S21 Ultra is not detected. Unlock it and reconnect its data-capable USB cable.'
    exit 2
}

if ($MatchingLine -match '\sunauthorized(?:\s|$)') {
    Write-Error 'The phone is detected but this computer is not authorized for USB debugging.'
    exit 3
}

if ($MatchingLine -notmatch '\sdevice(?:\s|$)') {
    Write-Error "The phone is not ready: $MatchingLine"
    exit 4
}

Write-Host 'Galaxy S21 Ultra connection: ready.'
if ($CheckOnly) {
    exit 0
}

$ExistingWindow = Get-Process -Name 'scrcpy' -ErrorAction SilentlyContinue |
    Where-Object { $_.MainWindowTitle -eq $WindowTitle } |
    Select-Object -First 1

if ($ExistingWindow) {
    Write-Host 'Pal phone-control window is already running.'
    exit 0
}

Start-Process -FilePath $ScrcpyPath -ArgumentList '-s', $SelectedSerial, '--no-audio', '--stay-awake', "--window-title=$WindowTitle"
Write-Host 'Opened the Pal phone-control window.'
