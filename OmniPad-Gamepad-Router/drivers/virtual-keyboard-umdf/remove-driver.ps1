param(
    [switch]$RemoveDevice,
    [string[]]$CertificateThumbprint = @()
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
    $devices = @(Get-PnpDevice -Class HIDClass -ErrorAction SilentlyContinue |
        Where-Object { $_.FriendlyName -eq 'OmniPad Virtual Keyboard Port (UMDF 2)' } |
        Where-Object {
        $ids = (Get-PnpDeviceProperty -InstanceId $_.InstanceId `
            -KeyName 'DEVPKEY_Device_HardwareIds' -ErrorAction SilentlyContinue).Data
        $ids -contains $hardwareId
    })
    $driverInfs = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($device in $devices) {
        $signedDriver = Get-CimInstance Win32_PnPSignedDriver -ErrorAction SilentlyContinue |
            Where-Object { $_.DeviceID -eq $device.InstanceId } |
            Select-Object -First 1
        if ($signedDriver.InfName -match '^oem\d+\.inf$') {
            $driverInfs.Add($signedDriver.InfName) | Out-Null
        }
        & pnputil.exe /remove-device $device.InstanceId
        if ($LASTEXITCODE -ne 0) {
            throw "PnPUtil could not remove exact device $($device.InstanceId) (exit $LASTEXITCODE)"
        }
        Write-Host "Removed exact device $($device.InstanceId)." -ForegroundColor Green
    }
    foreach ($driverInf in $driverInfs) {
        & pnputil.exe /delete-driver $driverInf /uninstall
        if ($LASTEXITCODE -ne 0) {
            throw "PnPUtil could not remove exact driver package $driverInf (exit $LASTEXITCODE)"
        }
        Write-Host "Removed exact driver-store package $driverInf." -ForegroundColor Green
    }
    if ($devices.Count -eq 0) {
        Write-Host "No installed device matched $hardwareId." -ForegroundColor Yellow
    }
}

foreach ($thumbprint in $CertificateThumbprint) {
    $normalizedThumbprint = ($thumbprint -replace '[^0-9A-Fa-f]', '').ToUpperInvariant()
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
