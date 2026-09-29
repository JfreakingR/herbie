<# Stop Herbie's desk face server. Close the fullscreen face itself with Alt+F4. #>
$ErrorActionPreference = 'Stop'
$PidFile = Join-Path $env:USERPROFILE '.herbie\desk.pid'
if (-not (Test-Path -LiteralPath $PidFile)) {
    Write-Host 'Herbie desk server is not running.'
    return
}
$deskPid = (Get-Content -LiteralPath $PidFile -Raw).Trim()
$process = Get-Process -Id $deskPid -ErrorAction SilentlyContinue
if ($process) { Stop-Process -Id $deskPid -Force }
Remove-Item -LiteralPath $PidFile -Force
Write-Host 'Herbie desk server stopped.'
