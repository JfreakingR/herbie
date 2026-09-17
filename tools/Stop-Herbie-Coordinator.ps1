<# Stop only the background process recorded by Start-Herbie-Coordinator.ps1. #>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$PidFile = Join-Path $env:USERPROFILE '.herbie\coordinator.pid'
$BrainPidFile = Join-Path $env:USERPROFILE '.herbie\pc-brain.pid'

if (Test-Path -LiteralPath $PidFile) {
    $coordinatorPid = [int](Get-Content -LiteralPath $PidFile -Raw).Trim()
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$coordinatorPid" -ErrorAction SilentlyContinue
    if ($process) {
        if ($process.CommandLine -notmatch 'herbie_coordinator\.py') {
            throw "PID $coordinatorPid does not belong to Herbie; refusing to stop it."
        }
        Stop-Process -Id $coordinatorPid
        Write-Host "Herbie coordinator stopped (PID $coordinatorPid)."
    }
    Remove-Item -LiteralPath $PidFile -Force
}

if (Test-Path -LiteralPath $BrainPidFile) {
    $brainPid = [int](Get-Content -LiteralPath $BrainPidFile -Raw).Trim()
    $brainProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$brainPid" -ErrorAction SilentlyContinue
    if ($brainProcess) {
        if ($brainProcess.CommandLine -notmatch 'herbie_pc_brain\.py') {
            throw "PID $brainPid does not belong to Herbie; refusing to stop it."
        }
        Stop-Process -Id $brainPid
        Write-Host "Herbie PC brain stopped (PID $brainPid)."
    }
    Remove-Item -LiteralPath $BrainPidFile -Force
}

Write-Host 'The phone will take over when the short computer lease expires.'
