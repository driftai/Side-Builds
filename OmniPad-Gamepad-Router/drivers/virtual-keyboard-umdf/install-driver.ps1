param(
    [string]$InfPath = ""
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$hardwareId = 'Root\OmniPadVirtualKeyboardUmdf'

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this installer from an elevated PowerShell window.'
}

if ([Environment]::OSVersion.Version.Build -lt 22000) {
    throw 'The UMDF HID path requires Windows 11 build 22000 or newer (MsHidUmdf.inf).'
}

if (-not $InfPath) {
    $candidate = Get-ChildItem -LiteralPath $root -Recurse -Filter 'OmniPadVirtualKeyboardUmdf.inf' -File |
        Where-Object { $_.FullName -match '\\x64\\Debug\\OmniPadVirtualKeyboardUmdf\\' } |
        Select-Object -First 1
    if (-not $candidate) {
        throw 'Packaged INF not found. Run build-driver.ps1 first.'
    }
    $InfPath = $candidate.FullName
}

$InfPath = (Resolve-Path -LiteralPath $InfPath).Path
$packageDirectory = Split-Path -Parent $InfPath
$catalog = Join-Path $packageDirectory 'OmniPadVirtualKeyboardUmdf.cat'
if (-not (Test-Path -LiteralPath $catalog)) {
    throw "Catalog not found: $catalog"
}
$signature = Get-AuthenticodeSignature -LiteralPath $catalog
if ($signature.Status -ne 'Valid') {
    throw "The catalog signature is not trusted ($($signature.Status)). Sign the package before installation."
}

$kitsTools = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\Tools'
$devcon = Get-ChildItem -LiteralPath $kitsTools -Recurse -Filter 'devcon.exe' -File |
    Where-Object { $_.FullName -match '\\x64\\devcon.exe$' } |
    Sort-Object FullName -Descending |
    Select-Object -First 1 -ExpandProperty FullName
if (-not $devcon) {
    throw 'x64 devcon.exe was not found in Windows Kits\10\Tools.'
}

Write-Host 'Installing the signed UMDF package without changing boot mode...' -ForegroundColor Cyan
$installedDevice = Get-PnpDevice -Class HIDClass -PresentOnly -ErrorAction SilentlyContinue |
    Where-Object { $_.FriendlyName -eq 'OmniPad Virtual Keyboard Port (UMDF 2)' } |
    Where-Object {
    $ids = (Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName 'DEVPKEY_Device_HardwareIds' -ErrorAction SilentlyContinue).Data
    $ids -contains $hardwareId
} | Select-Object -First 1
if ($installedDevice) {
    Write-Host "Updating existing device $($installedDevice.InstanceId)..." -ForegroundColor Cyan
    & $devcon update $InfPath $hardwareId
} else {
    & $devcon install $InfPath $hardwareId
}
if ($LASTEXITCODE -ne 0) {
    throw "DevCon installation failed with exit code $LASTEXITCODE"
}
Write-Host 'OmniPad Virtual Keyboard Port installed. No Test Mode or BCD change was made.' -ForegroundColor Green
