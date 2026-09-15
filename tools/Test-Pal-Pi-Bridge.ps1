[CmdletBinding()]
param(
    [string]$SshIdentity = 'C:\Users\Phyllis\.ssh\pal_melba_agent_ed25519',
    [string]$SshUser = 'jfreakingr',
    [string]$SshHost = 'Melba.local'
)

$ErrorActionPreference = 'Stop'
$ssh = 'C:\Windows\System32\OpenSSH\ssh.exe'
if (-not (Test-Path -LiteralPath $ssh)) {
    throw 'Windows OpenSSH client is missing.'
}
if (-not (Test-Path -LiteralPath $SshIdentity)) {
    throw "Missing Melba automation key: $SshIdentity"
}

$remotePython = @'
import json
import sys
import urllib.request

def call(path, data=None):
    req = urllib.request.Request(
        "http://127.0.0.1:8766" + path,
        data=data,
        method="GET" if data is None else "POST",
    )
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode())

health = call("/health")
heartbeat = call("/v1/heartbeat", b'{"source":"windows-ethernet-test"}')
print("SERVICE=" + str(health.get("service")))
print("VERSION=" + str(health.get("version")))
print("READY=" + str(health.get("ready")))
print("ACK=" + str(heartbeat.get("acknowledged")))
print("MOTOR=" + str(heartbeat.get("motor_authority")))
print("SAFE=" + str(heartbeat.get("safe_motion_state")))
ok = (
    health.get("ready") is True
    and heartbeat.get("acknowledged") is True
    and heartbeat.get("motor_authority") is False
    and heartbeat.get("safe_motion_state") == "STOP"
)
sys.exit(0 if ok else 2)
'@

$output = $remotePython | & $ssh -6 -i $SshIdentity -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=yes "${SshUser}@${SshHost}" "python3 -"
if ($LASTEXITCODE -ne 0) {
    throw "Pi bridge SSH health check failed with exit code $LASTEXITCODE"
}

$map = @{}
foreach ($line in $output) {
    if ($line -match '^(SERVICE|VERSION|READY|ACK|MOTOR|SAFE)=(.*)$') {
        $map[$matches[1]] = $matches[2]
    }
}

Write-Host "Service: $($map.SERVICE) $($map.VERSION)"
Write-Host "Ready: $($map.READY)"
Write-Host "Heartbeat acknowledged: $($map.ACK)"
Write-Host "Motor authority: $($map.MOTOR)"
Write-Host "Safe motion state: $($map.SAFE)"

if ($map.READY -ne 'True' -or $map.ACK -ne 'True' -or $map.MOTOR -ne 'False' -or $map.SAFE -ne 'STOP') {
    Write-Error 'Pal Pi bridge safety check failed.'
    exit 2
}
