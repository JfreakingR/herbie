[CmdletBinding()]
param(
    [string]$Ssid = '<WIFI_SSID>'
)

$ErrorActionPreference = 'Stop'

$adbPath = Join-Path $PSScriptRoot 'tools\scrcpy-win64-v4.1\scrcpy-win64-v4.1\adb.exe'
if (-not (Test-Path -LiteralPath $adbPath)) {
    throw "Bundled ADB was not found at: $adbPath"
}

function Invoke-PalAdb {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)

    $output = & $adbPath @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw ($output -join [Environment]::NewLine)
    }
    return @($output)
}

function Invoke-PalWpa {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)

    return Invoke-PalAdb shell wpa_cli '-p/data/misc/wifi/sockets' '-iwlan0' @Arguments
}

function Get-LastNonEmptyLine {
    param([object[]]$InputLines)

    return ($InputLines |
        ForEach-Object { $_.ToString().Trim() } |
        Where-Object { $_.Length -gt 0 } |
        Select-Object -Last 1)
}

Write-Host 'PAL USB Wi-Fi setup'
Write-Host "Network: $Ssid"
Write-Host 'The password will not be displayed or saved.'

$securePassword = Read-Host 'Enter the Wi-Fi password' -AsSecureString
$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
$passwordBytes = $null
$deriver = $null

try {
    $plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
    if ([string]::IsNullOrWhiteSpace($plainPassword)) {
        throw 'No password was entered.'
    }
    if ($plainPassword.Length -lt 8 -or $plainPassword.Length -gt 63) {
        throw 'A WPA/WPA2 password must contain 8 through 63 characters.'
    }

    $ssidBytes = [Text.Encoding]::UTF8.GetBytes($Ssid)
    $passwordBytes = [Text.Encoding]::UTF8.GetBytes($plainPassword)
    $plainPassword = $null

    $deriver = [Security.Cryptography.Rfc2898DeriveBytes]::new(
        $passwordBytes,
        $ssidBytes,
        4096,
        [Security.Cryptography.HashAlgorithmName]::SHA1
    )
    $pskHex = ([BitConverter]::ToString($deriver.GetBytes(32))).Replace('-', '').ToLowerInvariant()
    $ssidHex = ([BitConverter]::ToString($ssidBytes)).Replace('-', '').ToLowerInvariant()

    $devices = Invoke-PalAdb devices
    if (-not ($devices -match '0123456789ABCDEF\s+device')) {
        throw 'PAL is not currently visible as an authorized USB ADB device.'
    }

    Write-Host 'Enabling PAL Wi-Fi...'
    Invoke-PalAdb shell svc wifi enable | Out-Null
    Start-Sleep -Seconds 2

    $networkId = Get-LastNonEmptyLine (Invoke-PalWpa add_network)
    if ($networkId -notmatch '^\d+$') {
        throw "PAL did not create a Wi-Fi profile. Response: $networkId"
    }

    try {
        foreach ($setting in @(
            @('ssid', $ssidHex),
            @('psk', $pskHex),
            @('key_mgmt', 'WPA-PSK'),
            @('scan_ssid', '1')
        )) {
            $response = Get-LastNonEmptyLine (Invoke-PalWpa set_network $networkId $setting[0] $setting[1])
            if ($response -ne 'OK') {
                throw "PAL rejected Wi-Fi setting '$($setting[0])'. Response: $response"
            }
        }

        Invoke-PalWpa enable_network $networkId | Out-Null
        Invoke-PalWpa select_network $networkId | Out-Null
        $saveResponse = Get-LastNonEmptyLine (Invoke-PalWpa save_config)
        if ($saveResponse -ne 'OK') {
            Write-Warning 'PAL selected the network, but its Wi-Fi profile did not report a successful save.'
        }
    }
    catch {
        Invoke-PalWpa remove_network $networkId | Out-Null
        throw
    }

    Write-Host 'Waiting for PAL to connect...'
    Start-Sleep -Seconds 12
    $status = Invoke-PalWpa status
    $safeStatus = $status | Where-Object { $_ -notmatch '^(psk|password)=' }
    $safeStatus | ForEach-Object { Write-Host $_ }

    if ($status -match '^wpa_state=COMPLETED$') {
        Write-Host 'SUCCESS: PAL joined Wi-Fi.' -ForegroundColor Green
    }
    else {
        Write-Warning 'PAL has not completed the Wi-Fi connection yet. Leave USB connected for diagnosis.'
    }
}
finally {
    if ($deriver) { $deriver.Dispose() }
    if ($passwordBytes) { [Array]::Clear($passwordBytes, 0, $passwordBytes.Length) }
    if ($passwordPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
    }
}

Write-Host 'Press Enter to close.'
[void](Read-Host)
