[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$diskNumber = 3
$physicalPath = '\\.\PhysicalDrive3'
$expectedMinimumDiskSize = 62000000000
$expectedMaximumDiskSize = 63000000000
$imagePath = 'C:\Users\Phyllis\Desktop\Drive\Pal\tools\2026-06-18-raspios-trixie-arm64-lite.img'
$expectedImageSize = 2977955840
$expectedImageHash = 'E235FD24FC5F039C08DABA7D3ABC04AECC7313F979D16D2A3FDAD29DD44C33A9'
$statusPath = 'C:\Users\Phyllis\Desktop\Drive\Pal\tools\melba-raw-write-status.txt'
$bufferSize = 8MB

Set-Content -LiteralPath $statusPath -Value "STARTED=$(Get-Date -Format o)"

try {
    $targetDisk = Get-Disk -Number $diskNumber
    if (
        $targetDisk.FriendlyName -ne 'Generic STORAGE DEVICE' -or
        $targetDisk.BusType -ne 'USB' -or
        $targetDisk.Size -lt $expectedMinimumDiskSize -or
        $targetDisk.Size -gt $expectedMaximumDiskSize
    ) {
        throw 'Physical Disk 3 does not match the verified 64 GB USB microSD.'
    }

    $imageFile = Get-Item -LiteralPath $imagePath
    if ($imageFile.Length -ne $expectedImageSize) {
        throw 'The decompressed image size does not match.'
    }
    $actualImageHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $imagePath).Hash
    if ($actualImageHash -ne $expectedImageHash) {
        throw 'The decompressed image checksum does not match.'
    }

    Add-Content -LiteralPath $statusPath -Value 'TARGET_AND_IMAGE_VERIFIED=True'
    Clear-Disk -Number $diskNumber -RemoveData -RemoveOEM -Confirm:$false
    Add-Content -LiteralPath $statusPath -Value 'TARGET_CLEARED=True'

    $sourceStream = [System.IO.File]::Open($imagePath,[System.IO.FileMode]::Open,[System.IO.FileAccess]::Read,[System.IO.FileShare]::Read)
    $targetStream = [System.IO.File]::Open($physicalPath,[System.IO.FileMode]::Open,[System.IO.FileAccess]::Write,[System.IO.FileShare]::ReadWrite)
    try {
        $writeBuffer = New-Object byte[] $bufferSize
        $written = [int64]0
        $nextProgress = [int64](256MB)
        while (($bytesRead = $sourceStream.Read($writeBuffer,0,$writeBuffer.Length)) -gt 0) {
            $targetStream.Write($writeBuffer,0,$bytesRead)
            $written += $bytesRead
            if ($written -ge $nextProgress) {
                Set-Content -LiteralPath $statusPath -Value @(
                    "STARTED=$(Get-Date -Format o)"
                    'TARGET_AND_IMAGE_VERIFIED=True'
                    'TARGET_CLEARED=True'
                    "BYTES_WRITTEN=$written"
                )
                $nextProgress += [int64](256MB)
            }
        }
        $targetStream.Flush()
    } finally {
        $targetStream.Dispose()
        $sourceStream.Dispose()
    }
    if ($written -ne $expectedImageSize) {
        throw "Raw write byte count mismatch: $written."
    }
    Add-Content -LiteralPath $statusPath -Value "WRITE_COMPLETE_BYTES=$written"

    $verifyStream = [System.IO.File]::Open($physicalPath,[System.IO.FileMode]::Open,[System.IO.FileAccess]::Read,[System.IO.FileShare]::ReadWrite)
    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        $verifyBuffer = New-Object byte[] $bufferSize
        $verifiedBytes = [int64]0
        while ($verifiedBytes -lt $expectedImageSize) {
            $remaining = $expectedImageSize - $verifiedBytes
            $requested = [int][Math]::Min($verifyBuffer.Length,$remaining)
            $bytesRead = $verifyStream.Read($verifyBuffer,0,$requested)
            if ($bytesRead -le 0) {
                throw 'Unexpected end of device during verification.'
            }
            [void]$sha256.TransformBlock($verifyBuffer,0,$bytesRead,$verifyBuffer,0)
            $verifiedBytes += $bytesRead
        }
        [void]$sha256.TransformFinalBlock((New-Object byte[] 0),0,0)
        $deviceHash = ([BitConverter]::ToString($sha256.Hash)).Replace('-','')
    } finally {
        $sha256.Dispose()
        $verifyStream.Dispose()
    }
    if ($deviceHash -ne $expectedImageHash) {
        throw "Read-back checksum mismatch: $deviceHash."
    }

    Add-Content -LiteralPath $statusPath -Value "READBACK_SHA256=$deviceHash"
    Add-Content -LiteralPath $statusPath -Value 'RAW_WRITE_VERIFIED=True'
    Add-Content -LiteralPath $statusPath -Value "FINISHED=$(Get-Date -Format o)"
} catch {
    Add-Content -LiteralPath $statusPath -Value "FAILED=$($_.Exception.Message)"
    exit 1
}
