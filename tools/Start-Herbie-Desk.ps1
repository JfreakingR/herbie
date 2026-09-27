<# Herbie as a desk bot: start the desk face server and open it fullscreen on the 7" LCD.

   The LCD is found as the smallest monitor that is not the primary one. Pass
   -Monitor <n> (0-based, in the order Windows lists them) to pick another, or
   -List to print what Windows sees. -Voice screen makes the face speak through
   the PC/monitor audio instead of the Galaxy's speaker. #>
[CmdletBinding()]
param(
    [int]$Monitor = -1,
    [ValidateSet('galaxy', 'screen')][string]$Voice = 'galaxy',
    [int]$Port = 8766,
    [switch]$List
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
$screens = [System.Windows.Forms.Screen]::AllScreens

if ($List) {
    for ($i = 0; $i -lt $screens.Count; $i++) {
        $s = $screens[$i]
        $b = $s.Bounds
        Write-Host ("{0}: {1}x{2} at {3},{4}{5}" -f $i, $b.Width, $b.Height, $b.X, $b.Y,
            $(if ($s.Primary) { '  (primary)' } else { '' }))
    }
    return
}

$Root = Split-Path $PSScriptRoot -Parent
$Server = Join-Path $Root 'desk\herbie_desk.py'
$PrivateDirectory = Join-Path $env:USERPROFILE '.herbie'
$LogFile = Join-Path $PrivateDirectory 'desk.log'
$ErrorLog = Join-Path $PrivateDirectory 'desk-error.log'
$PidFile = Join-Path $PrivateDirectory 'desk.pid'
$BrowserProfile = Join-Path $PrivateDirectory 'desk-browser'
$Url = "http://127.0.0.1:$Port/face/?kiosk=1"
New-Item -ItemType Directory -Path $PrivateDirectory -Force | Out-Null

$pythonCandidates = @(
    (Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe')
)
$Python = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $Python) {
    $command = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($command) { $Python = $command.Source }
}
if (-not $Python) { throw 'Python was not found.' }

function Get-DeskHealth {
    try { Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 2 } catch { $null }
}

$health = Get-DeskHealth
if ($health -and $health.service -ne 'herbie-desk') {
    throw "Port $Port is already used by something else (the old Grok face server?). Close it, or pass -Port."
}
if (-not $health) {
    $process = Start-Process -FilePath $Python `
        -ArgumentList @("`"$Server`"", '--voice', $Voice, '--port', $Port) `
        -WindowStyle Hidden -RedirectStandardOutput $LogFile -RedirectStandardError $ErrorLog -PassThru
    [System.IO.File]::WriteAllText($PidFile, "$($process.Id)`n")
    for ($i = 0; $i -lt 40 -and -not (Get-DeskHealth); $i++) { Start-Sleep -Milliseconds 250 }
    if (-not (Get-DeskHealth)) {
        Get-Content -LiteralPath $ErrorLog -ErrorAction SilentlyContinue | Write-Host
        throw "Herbie's desk server did not start. See $ErrorLog"
    }
}
$problems = Get-Content -LiteralPath $ErrorLog -ErrorAction SilentlyContinue
if ($problems) { $problems | ForEach-Object { Write-Warning $_ } }

if ($Monitor -ge 0) {
    if ($Monitor -ge $screens.Count) { throw "There is no monitor $Monitor. Run with -List." }
    $target = $screens[$Monitor]
} else {
    $target = $screens | Where-Object { -not $_.Primary } |
        Sort-Object { $_.Bounds.Width * $_.Bounds.Height } | Select-Object -First 1
    if (-not $target) {
        Write-Warning 'Only one monitor is connected; showing the face on it. Plug in the 7" LCD and run again.'
        $target = $screens[0]
    }
}
$b = $target.Bounds
Write-Host ("Herbie's face -> {0}x{1} monitor at {2},{3}" -f $b.Width, $b.Height, $b.X, $b.Y)

$browser = @(
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
if (-not $browser) { throw 'Neither Edge nor Chrome was found.' }

# A separate profile keeps this window out of your normal browser session, so
# --kiosk and the window position are honoured. Alt+F4 closes it.
Start-Process -FilePath $browser -ArgumentList @(
    "--user-data-dir=`"$BrowserProfile`"",
    "--window-position=$($b.X),$($b.Y)",
    "--window-size=$($b.Width),$($b.Height)",
    '--kiosk', $Url,
    '--edge-kiosk-type=fullscreen',
    '--no-first-run',
    '--autoplay-policy=no-user-gesture-required'
)
Write-Host "Herbie is on the desk. Type on the keyboard (or tap the face) to talk to him."
