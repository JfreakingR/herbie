[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$diskNumber = 3
$expectedMinimumSize = 62000000000
$expectedMaximumSize = 63000000000
$imagePath = 'C:\Users\Phyllis\Desktop\Drive\Pal\tools\2026-06-18-raspios-trixie-arm64-lite.img.xz'
$imagerPath = 'C:\Program Files\Raspberry Pi Ltd\Imager\rpi-imager.exe'
$expectedHash = 'ACFF736CA7945E3B305F07CDA4ABDB870910E12634991DA69783611756E381B3'
$statusPath = 'C:\Users\Phyllis\Desktop\Drive\Pal\tools\melba-flash-status.txt'
$stdoutPath = 'C:\Users\Phyllis\Desktop\Drive\Pal\tools\melba-imager-stdout.txt'
$stderrPath = 'C:\Users\Phyllis\Desktop\Drive\Pal\tools\melba-imager-stderr.txt'

Set-Content -LiteralPath $statusPath -Value "STARTED=$(Get-Date -Format o)"

try {
    $targetDisk = Get-Disk -Number $diskNumber
    if (
        $targetDisk.FriendlyName -ne 'Generic STORAGE DEVICE' -or
        $targetDisk.BusType -ne 'USB' -or
        $targetDisk.Size -lt $expectedMinimumSize -or
        $targetDisk.Size -gt $expectedMaximumSize
    ) {
        throw 'Physical Disk 3 does not match the verified 64 GB USB microSD.'
    }

    $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $imagePath).Hash
    if ($actualHash -ne $expectedHash) {
        throw 'The Raspberry Pi OS image checksum does not match.'
    }

    $imagerArguments = @(
        '--cli'
        '--debug'
        '--sha256'
        $expectedHash
        $imagePath
        '\\.\PhysicalDrive3'
    )

    Add-Content -LiteralPath $statusPath -Value 'IMAGER_STARTED=True'
    Remove-Item -LiteralPath $stdoutPath,$stderrPath -Force -ErrorAction SilentlyContinue
    $imagerProcess = Start-Process -FilePath $imagerPath -ArgumentList $imagerArguments -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -Wait -PassThru
    Add-Content -LiteralPath $statusPath -Value "IMAGER_EXIT_CODE=$($imagerProcess.ExitCode)"
    if ($imagerProcess.ExitCode -ne 0) {
        throw "Raspberry Pi Imager failed with exit code $($imagerProcess.ExitCode)."
    }

    Add-Content -LiteralPath $statusPath -Value 'IMAGING_COMPLETE=True'
    Add-Content -LiteralPath $statusPath -Value "FINISHED=$(Get-Date -Format o)"
} catch {
    Add-Content -LiteralPath $statusPath -Value "FAILED=$($_.Exception.Message)"
    exit 1
}
