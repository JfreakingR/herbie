<# Start Herbie's computer-primary lease coordinator in the background. #>
[CmdletBinding()]
param([string]$Phone)

$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$Coordinator = Join-Path $Root 'computer_brain\herbie_coordinator.py'
$PcBrain = Join-Path $Root 'computer_brain\herbie_pc_brain.py'
$PrivateDirectory = Join-Path $env:USERPROFILE '.herbie'
$PidFile = Join-Path $PrivateDirectory 'coordinator.pid'
$LogFile = Join-Path $PrivateDirectory 'coordinator.log'
$ErrorLog = Join-Path $PrivateDirectory 'coordinator-error.log'
$BrainPidFile = Join-Path $PrivateDirectory 'pc-brain.pid'
$BrainLogFile = Join-Path $PrivateDirectory 'pc-brain.log'
$BrainErrorLog = Join-Path $PrivateDirectory 'pc-brain-error.log'

$pythonCandidates = @(
    'C:\Users\Phyllis\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
)
$Python = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $Python) {
    $command = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($command) { $Python = $command.Source }
}
if (-not $Python) { throw 'Python was not found.' }
if (-not (Test-Path -LiteralPath $Coordinator)) { throw "Missing coordinator: $Coordinator" }
if (-not (Test-Path -LiteralPath $PcBrain)) { throw "Missing PC brain: $PcBrain" }

New-Item -ItemType Directory -Path $PrivateDirectory -Force | Out-Null

if (Test-Path -LiteralPath $BrainPidFile) {
    $oldBrainPid = (Get-Content -LiteralPath $BrainPidFile -Raw).Trim()
    $oldBrain = Get-Process -Id $oldBrainPid -ErrorAction SilentlyContinue
    if (-not $oldBrain) { Remove-Item -LiteralPath $BrainPidFile -Force }
}
if (-not (Test-Path -LiteralPath $BrainPidFile)) {
    $brainProcess = Start-Process -FilePath $Python -ArgumentList @($PcBrain) `
        -WindowStyle Hidden -RedirectStandardOutput $BrainLogFile `
        -RedirectStandardError $BrainErrorLog -PassThru
    [System.IO.File]::WriteAllText($BrainPidFile, "$($brainProcess.Id)`n")
    Start-Sleep -Seconds 2
    if (-not (Get-Process -Id $brainProcess.Id -ErrorAction SilentlyContinue)) {
        throw "Herbie PC brain stopped during startup. Check $BrainErrorLog"
    }
    try {
        $health = Invoke-RestMethod -Uri 'http://127.0.0.1:18766/health' -TimeoutSec 5
        if (-not $health.ready -or $health.motor_authority) {
            throw 'PC brain health response failed its safety check.'
        }
    } catch {
        Stop-Process -Id $brainProcess.Id -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $BrainPidFile -Force -ErrorAction SilentlyContinue
        throw
    }
    Write-Host "Herbie PC language brain started as PID $($brainProcess.Id)." -ForegroundColor Green
}

if (Test-Path -LiteralPath $PidFile) {
    $oldPid = (Get-Content -LiteralPath $PidFile -Raw).Trim()
    $oldProcess = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
    if ($oldProcess) {
        Write-Host "Herbie coordinator is already running as PID $oldPid."
        exit 0
    }
    Remove-Item -LiteralPath $PidFile -Force
}

$arguments = @($Coordinator)
if ($Phone) { $arguments += @('--phone', $Phone) }
$process = Start-Process -FilePath $Python -ArgumentList $arguments `
    -WindowStyle Hidden -RedirectStandardOutput $LogFile `
    -RedirectStandardError $ErrorLog -PassThru
[System.IO.File]::WriteAllText($PidFile, "$($process.Id)`n")

Start-Sleep -Seconds 7
if (-not (Get-Process -Id $process.Id -ErrorAction SilentlyContinue)) {
    throw "Herbie coordinator stopped during startup. Check $ErrorLog"
}
Write-Host "Herbie computer coordinator started as PID $($process.Id)." -ForegroundColor Green
Write-Host "Log: $LogFile"
Write-Host "PC brain log: $BrainLogFile"
