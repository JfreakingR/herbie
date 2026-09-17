<#
.SYNOPSIS
    Export Herbie's live phone memory to a private Windows backup.

.DESCRIPTION
    Uses the already-authorized ADB connection and Herbie's bearer token to
    request /v1/export. The resulting JSON stays on this computer under the
    current Windows user's private .herbie directory. The token is never
    printed or copied into the backup.

    This is deliberately read-only on the phone. It does not restart Termux,
    change Android settings, or touch motor control.
#>
[CmdletBinding()]
param(
    [string]$DeviceSerial = 'R5CR11QCHPY',
    [string]$AdbPath,
    [string]$BackupDirectory = (Join-Path $env:USERPROFILE '.herbie\backups'),
    [int]$ForwardPort = 18765
)

$ErrorActionPreference = 'Stop'

function Resolve-HerbieAdb {
    if ($AdbPath) {
        if (-not (Test-Path -LiteralPath $AdbPath)) {
            throw "ADB was not found at $AdbPath"
        }
        return (Resolve-Path -LiteralPath $AdbPath).Path
    }

    $candidates = @(
        (Join-Path $PSScriptRoot 'scrcpy-win64-v4.1\scrcpy-win64-v4.1\adb.exe'),
        (Join-Path $env:USERPROFILE 'Desktop\Drive\Pal\tools\scrcpy-win64-v4.1\scrcpy-win64-v4.1\adb.exe')
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    $command = Get-Command adb.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    throw 'ADB is not installed in the current Herbie tools folder and was not found on PATH.'
}

function Protect-ForCurrentUser {
    param([Parameter(Mandatory)][string]$Path)

    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    if (Test-Path -LiteralPath $Path -PathType Container) {
        $grant = "$identity`:(OI)(CI)F"
    } else {
        $grant = "$identity`:F"
    }
    & icacls.exe $Path /inheritance:r /grant:r $grant | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Could not restrict backup permissions for $Path"
    }
}

$resolvedAdb = Resolve-HerbieAdb
$tokenFile = Join-Path $env:USERPROFILE '.herbie\api-token'
if (-not (Test-Path -LiteralPath $tokenFile)) {
    throw "Herbie's API token is missing. Run Export-Herbie-Token.ps1 first."
}
$apiToken = (Get-Content -LiteralPath $tokenFile -Raw).Trim()
if ($apiToken.Length -lt 8) { throw 'Herbie API token is invalid or empty.' }

$deviceLines = & $resolvedAdb devices -l
$devicePattern = '^' + [regex]::Escape($DeviceSerial) + '\s+device\b'
$connected = $deviceLines | Where-Object { $_ -match $devicePattern } | Select-Object -First 1
if (-not $connected) {
    throw "Galaxy $DeviceSerial is not attached and authorized over ADB."
}

$forwardSpec = "tcp:$ForwardPort"
& $resolvedAdb -s $DeviceSerial forward $forwardSpec tcp:8765 | Out-Null
try {
    $headers = @{ Authorization = "Bearer $apiToken" }
    $baseUri = "http://127.0.0.1:$ForwardPort"
    $health = Invoke-RestMethod -Uri "$baseUri/health" -Headers $headers -TimeoutSec 10
    if (-not $health.ready) { throw 'Herbie answered, but the phone brain is not ready.' }
    if ($health.motor_authority -or $health.safe_motion_state -ne 'STOP') {
        throw 'Safety check failed; backup stopped.'
    }

    $export = Invoke-RestMethod -Uri "$baseUri/v1/export?include_inactive=true" `
        -Headers $headers -TimeoutSec 30
    $json = $export | ConvertTo-Json -Depth 20

    New-Item -ItemType Directory -Path $BackupDirectory -Force | Out-Null
    Protect-ForCurrentUser -Path $BackupDirectory

    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $backupFile = Join-Path $BackupDirectory "herbie-memory-$stamp.json"
    [System.IO.File]::WriteAllText($backupFile, $json + "`n", [System.Text.UTF8Encoding]::new($false))

    Protect-ForCurrentUser -Path $backupFile
    $hash = (Get-FileHash -LiteralPath $backupFile -Algorithm SHA256).Hash

    Write-Host "Herbie backup complete." -ForegroundColor Green
    Write-Host "File:    $backupFile"
    Write-Host "Version: $($health.version)"
    Write-Host "SHA-256: $hash"
    Write-Host 'The API token was not included.'
} finally {
    & $resolvedAdb -s $DeviceSerial forward --remove $forwardSpec 2>$null
    $apiToken = $null
}
