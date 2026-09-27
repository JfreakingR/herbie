[CmdletBinding()]
param(
    [string]$Port = 'COM7',
    [string]$Ssid = 'MySpectrumWiFi20-2G_EXT'
)

$ErrorActionPreference = 'Stop'

function Read-SerialUntil {
    param(
        [IO.Ports.SerialPort]$Serial,
        [int]$Seconds,
        [string]$Secret,
        [string]$StopPattern = ''
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($Seconds)
    $allText = ''
    while ([DateTime]::UtcNow -lt $deadline) {
        $text = $Serial.ReadExisting()
        if ($text) {
            $allText += $text
            $safeText = if ($Secret) { $text.Replace($Secret, '********') } else { $text }
            Write-Host -NoNewline $safeText
            if ($StopPattern -and $allText -match $StopPattern) { break }
        }
        Start-Sleep -Milliseconds 100
    }
    return $allText
}

Write-Host 'Herbie factory BLE provisioning'
Write-Host "ESP32 port: $Port"
Write-Host "Network: $Ssid"
Write-Host 'The password will not be displayed or saved.'

$securePassword = Read-Host 'Enter the Wi-Fi password' -AsSecureString
$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
$serial = $null

try {
    $plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
    if ([string]::IsNullOrWhiteSpace($plainPassword)) { throw 'No password was entered.' }

    $serial = [IO.Ports.SerialPort]::new($Port, 115200, 'None', 8, 'One')
    $serial.DtrEnable = $false
    $serial.RtsEnable = $false
    $serial.Handshake = 'None'
    $serial.NewLine = "`n"
    $serial.ReadTimeout = 250
    $serial.Open()

    [void](Read-SerialUntil $serial 2 $plainPassword)
    Write-Host "`nScanning for Herbie..."
    $serial.WriteLine('SCAN')
    $scanText = Read-SerialUntil $serial 25 $plainPassword 'Using write char|Connect failed|Target not found'
    if ($scanText -notmatch 'Using write char') {
        throw "The ESP32 did not establish a writable BLE connection to Herbie."
    }

    $serial.WriteLine("SSID=$Ssid")
    $serial.WriteLine("PASS=$plainPassword")
    Start-Sleep -Milliseconds 500
    [void](Read-SerialUntil $serial 2 $plainPassword)

    Write-Host "`nSending the recovered factory setwifi request to Herbie..."
    $serial.WriteLine('SEND')
    $sendText = Read-SerialUntil $serial 20 $plainPassword 'SEND wait finished'
    if ($sendText -notmatch 'SEND factory framing complete ok=1') {
        throw 'The ESP32 did not complete all factory-framed BLE writes.'
    }
    Write-Host "`nFactory BLE request sent successfully." -ForegroundColor Green
}
finally {
    if ($serial -and $serial.IsOpen) { $serial.Close() }
    if ($serial) { $serial.Dispose() }
    if ($passwordPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
    }
}
