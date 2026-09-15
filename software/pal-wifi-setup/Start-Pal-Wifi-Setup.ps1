$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here
$venvPython = Join-Path $here ".venv\Scripts\python.exe"
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Error "Python was not found. Install Python 3, then run this script again."
}
if (-not (Test-Path $venvPython)) {
    Write-Host "Creating local Python environment..."
    & python -m venv (Join-Path $here ".venv")
}
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $here "requirements.txt")
& $venvPython (Join-Path $here "pal_wifi_setup.py")
