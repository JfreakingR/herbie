[CmdletBinding()]
param(
    [string]$Ssid = 'MySpectrumWiFi20-2G_EXT'
)

$ErrorActionPreference = 'Stop'
$adbPath = Join-Path $PSScriptRoot 'tools\scrcpy-win64-v4.1\scrcpy-win64-v4.1\adb.exe'
$remotePrefs = '/data/data/com.sego.toy.ctl/shared_prefs/com.sego.toy.ctl_preferences.xml'
$remoteBackup = '/data/local/tmp/com.sego.toy.ctl_preferences.before-usb-wifi.xml'

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

function Set-StringPreference {
    param([xml]$Document, [string]$Name, [string]$Value)

    $oldNode = $Document.map.ChildNodes | Where-Object { $_.name -eq $Name } | Select-Object -First 1
    if ($oldNode) { [void]$Document.map.RemoveChild($oldNode) }
    $newNode = $Document.CreateElement('string')
    $newNode.SetAttribute('name', $Name)
    $newNode.InnerText = $Value
    [void]$Document.map.AppendChild($newNode)
}

function Set-IntegerPreference {
    param([xml]$Document, [string]$Name, [int]$Value)

    $oldNode = $Document.map.ChildNodes | Where-Object { $_.name -eq $Name } | Select-Object -First 1
    if ($oldNode) { [void]$Document.map.RemoveChild($oldNode) }
    $newNode = $Document.CreateElement('int')
    $newNode.SetAttribute('name', $Name)
    $newNode.SetAttribute('value', $Value.ToString([Globalization.CultureInfo]::InvariantCulture))
    [void]$Document.map.AppendChild($newNode)
}

function Write-RemoteTextFromMemory {
    param([string]$RemotePath, [string]$Text)

    $startInfo = [Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $adbPath
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardInput = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.Arguments = "shell sh -c `"cat > $RemotePath`""

    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    if (-not $process.Start()) { throw 'Could not start the ADB writer.' }
    try {
        $process.StandardInput.Write($Text)
        $process.StandardInput.Close()
        $standardOutput = $process.StandardOutput.ReadToEnd()
        $standardError = $process.StandardError.ReadToEnd()
        $process.WaitForExit()
        if ($process.ExitCode -ne 0) {
            throw (($standardOutput, $standardError | Where-Object { $_ }) -join [Environment]::NewLine)
        }
    }
    finally {
        $process.Dispose()
    }
}

Write-Host 'PAL factory Wi-Fi completion'
Write-Host "Network: $Ssid"
Write-Host 'The password will not be displayed or saved on this computer.'

$securePassword = Read-Host 'Enter the Wi-Fi password' -AsSecureString
$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)

try {
    $plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
    if ([string]::IsNullOrWhiteSpace($plainPassword)) { throw 'No password was entered.' }
    if ($plainPassword.Length -lt 8 -or $plainPassword.Length -gt 63) {
        throw 'A WPA/WPA2 password must contain 8 through 63 characters.'
    }

    $devices = Invoke-PalAdb devices
    if (-not ($devices -match '0123456789ABCDEF\s+device')) {
        throw 'PAL is not currently visible as an authorized USB ADB device.'
    }

    $preferenceText = (Invoke-PalAdb shell cat $remotePrefs) -join "`n"
    [xml]$preferenceXml = $preferenceText
    Set-StringPreference $preferenceXml 'config_wifi_ssid' $Ssid
    Set-IntegerPreference $preferenceXml 'config_wifi_security' 1
    Set-StringPreference $preferenceXml 'config_wifi_password' $plainPassword

    $writerSettings = [Xml.XmlWriterSettings]::new()
    $writerSettings.Encoding = [Text.UTF8Encoding]::new($false)
    $writerSettings.Indent = $true
    $stringBuilder = [Text.StringBuilder]::new()
    $xmlWriter = [Xml.XmlWriter]::Create($stringBuilder, $writerSettings)
    try { $preferenceXml.Save($xmlWriter) } finally { $xmlWriter.Dispose() }
    $updatedText = $stringBuilder.ToString()

    Write-Host 'Backing up PAL factory preferences and stopping the controller service...'
    Invoke-PalAdb shell cp $remotePrefs $remoteBackup | Out-Null
    Invoke-PalAdb shell chmod 600 $remoteBackup | Out-Null
    Invoke-PalAdb shell am force-stop com.sego.toy.ctl | Out-Null

    try {
        Write-RemoteTextFromMemory $remotePrefs $updatedText
        Invoke-PalAdb shell chown 10038:10038 $remotePrefs | Out-Null
        Invoke-PalAdb shell chmod 660 $remotePrefs | Out-Null
    }
    catch {
        Invoke-PalAdb shell cp $remoteBackup $remotePrefs | Out-Null
        Invoke-PalAdb shell chown 10038:10038 $remotePrefs | Out-Null
        Invoke-PalAdb shell chmod 660 $remotePrefs | Out-Null
        throw
    }

    $plainPassword = $null
    $updatedText = $null
    $preferenceText = $null

    Write-Host 'Restarting PAL factory controller...'
    Invoke-PalAdb shell am startservice -n com.sego.toy.ctl/.BootService | Out-Null
    Start-Sleep -Seconds 3
    Invoke-PalAdb shell am startservice -n com.sego.toy.ctl/.CtlService | Out-Null

    Write-Host 'Factory Wi-Fi fields updated. Leave USB connected while the connection is verified.' -ForegroundColor Green
}
finally {
    if ($passwordPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
    }
}

Write-Host 'Press Enter to close.'
[void](Read-Host)
