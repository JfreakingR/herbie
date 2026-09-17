<# Install or remove the current-user logon task for Herbie's coordinator. #>
[CmdletBinding()]
param([switch]$Remove)

$ErrorActionPreference = 'Stop'
$TaskName = 'Herbie Computer Coordinator'

if ($Remove) {
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host 'Herbie coordinator autostart removed.'
    } else {
        Write-Host 'Herbie coordinator autostart was not installed.'
    }
    exit 0
}

$startScript = Join-Path $PSScriptRoot 'Start-Herbie-Coordinator.ps1'
if (-not (Test-Path -LiteralPath $startScript)) {
    throw "Missing coordinator starter: $startScript"
}

$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$escapedScript = $startScript.Replace('"', '\"')
$arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$escapedScript`""
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $identity
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero)
$task = New-ScheduledTask -Action $action -Trigger $trigger -Principal $principal -Settings $settings `
    -Description 'Keeps the home computer primary while Herbie automatically falls back to the Galaxy.'
Register-ScheduledTask -TaskName $TaskName -InputObject $task -Force | Out-Null

$installed = Get-ScheduledTask -TaskName $TaskName
Write-Host "Herbie coordinator autostart installed: $($installed.TaskName)" -ForegroundColor Green
Write-Host "State: $($installed.State)"
