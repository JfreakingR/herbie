$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent (Split-Path -Parent $here)
$cli = Join-Path $root "tools\arduino-cli\arduino-cli.exe"
$cfg = Join-Path $root "tools\arduino-cli\arduino-cli.yaml"
$sketch = Join-Path $root "firmware\pal_ble_wifi"
$port = "COM7"
$fqbn = "esp32:esp32:esp32"
if (-not (Test-Path $cli)) { throw "arduino-cli not found: $cli" }
Write-Host "Compiling $sketch"
& $cli compile --config-file $cfg --fqbn $fqbn $sketch
if ($LASTEXITCODE -ne 0) { throw "compile failed" }
Write-Host "Uploading to $port"
& $cli upload --config-file $cfg --fqbn $fqbn -p $port $sketch
if ($LASTEXITCODE -ne 0) { throw "upload failed" }
Write-Host "Flash OK. Open serial 115200 and type SCAN"
