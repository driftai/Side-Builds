param(
    [switch]$RemoveDevice,
    [string]$CertificateThumbprint = ""
)

$ErrorActionPreference = 'Stop'
$hardwareId = 'Root\OmniPadVirtualKeyboardUmdf'

if (-not $RemoveDevice -and -not $CertificateThumbprint) {
    throw 'Specify -RemoveDevice and/or the exact -CertificateThumbprint to remove.'
}
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this removal step from an elevated PowerShell window.'
}

if ($RemoveDevice) {
    $kitsTools = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\Tools'
    $devcon = Get-ChildItem -LiteralPath $kitsTools -Recurse -Filter 'devcon.exe' -File |
        Where-Object { $_.FullName -match '\\x64\\devcon.exe$' } |
        Sort-Object FullName -Descending |
        Select-Object -First 1 -ExpandProperty FullName
    if (-not $devcon) {
        throw 'x64 devcon.exe was not found in Windows Kits\10\Tools.'
    }
    & $devcon remove $hardwareId
    if ($LASTEXITCODE -ne 0) {
        throw "DevCon removal failed with exit code $LASTEXITCODE"
    }
    Write-Host "Removed device matching $hardwareId." -ForegroundColor Green
}

if ($CertificateThumbprint) {
    $normalizedThumbprint = ($CertificateThumbprint -replace '[^0-9A-Fa-f]', '').ToUpperInvariant()
    if ($normalizedThumbprint.Length -ne 40 -and $normalizedThumbprint.Length -ne 64) {
        throw 'Certificate thumbprint must be the exact 40- or 64-character hexadecimal value recorded during signing.'
    }
    foreach ($storeName in @('My', 'Root', 'TrustedPublisher')) {
        $certificatePath = "Cert:\LocalMachine\$storeName\$normalizedThumbprint"
        if (Test-Path -LiteralPath $certificatePath) {
            Remove-Item -LiteralPath $certificatePath -Force
            Write-Host "Removed certificate $normalizedThumbprint from LocalMachine\$storeName." -ForegroundColor Green
        }
    }
}
