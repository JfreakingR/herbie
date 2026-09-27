[CmdletBinding()]
param(
    # Overrides the token normally read off the phone. Avoid passing this on a
    # shared machine: command lines are visible to other processes.
    [string]$ApiToken
)

$ErrorActionPreference = 'Stop'
$ToolDirectory = Join-Path $PSScriptRoot 'scrcpy-win64-v4.1\scrcpy-win64-v4.1'
$AdbPath = Join-Path $ToolDirectory 'adb.exe'
$AdbKeyPath = 'C:\Users\Phyllis\.android\adbkey'
$DeviceSerial = 'R5CR11QCHPY'

if (-not (Test-Path -LiteralPath $AdbPath)) {
    Write-Error "ADB is missing from $ToolDirectory"
    exit 1
}
if (-not (Test-Path -LiteralPath $AdbKeyPath)) {
    Write-Error "The saved Android authorization key is missing from $AdbKeyPath"
    exit 1
}

$env:ADB_VENDOR_KEYS = $AdbKeyPath
$env:ANDROID_USER_HOME = 'C:\Users\Phyllis\.android'

# -join first: `-notmatch` against an array returns the non-matching
# ELEMENTS, not a boolean, so the header line alone would make this fire.
$attached = (& $AdbPath devices) -join "`n"
if ($attached -notmatch ([regex]::Escape($DeviceSerial) + '\s+device')) {
    Write-Error "Galaxy $DeviceSerial is not attached over ADB. Re-seat the USB cable."
    exit 1
}

& $AdbPath -s $DeviceSerial forward tcp:18765 tcp:8765 | Out-Null

# The brain requires a bearer token. Termux's home is private to the Termux
# UID, so `adb shell cat` cannot read it - the token has to be exported once by
# Export-Herbie-Token.ps1, which stores it locally for this user only.
if (-not $ApiToken) {
    $tokenFile = Join-Path $env:USERPROFILE '.herbie\api-token'
    if (Test-Path -LiteralPath $tokenFile) {
        $ApiToken = (Get-Content -LiteralPath $tokenFile -Raw).Trim()
    }
}
if (-not $ApiToken) {
    Write-Error @'
No API token available.

Herbie 0.5.0 requires one on every endpoint except /health. Export it once with:

    powershell -File "<this folder>\Export-Herbie-Token.ps1"

or pass -ApiToken explicitly (avoid on a shared machine: command lines are
visible to other processes).
'@
    exit 1
}
$AuthHeader = @{ Authorization = "Bearer $ApiToken" }

$health = Invoke-RestMethod -Uri 'http://127.0.0.1:18765/health' -Headers $AuthHeader -TimeoutSec 5
$heartbeatBody = @{ source = 'windows-recovery-test' } | ConvertTo-Json -Compress
$heartbeat = Invoke-RestMethod -Uri 'http://127.0.0.1:18765/v1/heartbeat' -Method Post -Headers $AuthHeader -ContentType 'application/json' -Body $heartbeatBody -TimeoutSec 5

Write-Host "Service: $($health.service) $($health.version)"
Write-Host "Ready: $($health.ready)"
Write-Host "Memories: $($health.memory_count)"
Write-Host "Heartbeat acknowledged: $($heartbeat.acknowledged)"
Write-Host "Motor authority: $($heartbeat.motor_authority)"
Write-Host "Safe motion state: $($heartbeat.safe_motion_state)"

# An unauthenticated caller must not be able to reach anything that matters.
try {
    Invoke-RestMethod -Uri 'http://127.0.0.1:18765/v1/self' -TimeoutSec 5 | Out-Null
    Write-Error 'SECURITY: /v1/self answered without a token.'
    exit 3
} catch {
    if ($_.Exception.Response.StatusCode.value__ -ne 401) {
        Write-Error "Expected HTTP 401 for an untokened request, got $($_.Exception.Response.StatusCode.value__)."
        exit 3
    }
    Write-Host 'Auth check: untokened request correctly rejected (401)'
}

if (-not $health.ready -or -not $heartbeat.acknowledged -or $heartbeat.motor_authority -or $heartbeat.safe_motion_state -ne 'STOP') {
    Write-Error 'Herbie phone brain safety check failed.'
    exit 2
}
