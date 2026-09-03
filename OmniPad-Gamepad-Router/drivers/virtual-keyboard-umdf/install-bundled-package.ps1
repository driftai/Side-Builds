param(
    [switch]$TrustBundledCertificate
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$package = Join-Path $root 'package\x64'
$hardwareId = 'Root\OmniPadVirtualKeyboardUmdf'
$certificateSubject = 'CN=OmniPad Local UMDF Development'
$expectedThumbprint = '5631FB22CE4E3E6512CAADE65B4F5963644BB56D'
$expectedHashes = @{
    'OmniPadVirtualKeyboardUmdf.dll' = 'DF426D4AB25B0F8DB55DADFF710B0FACB481FF7E1684F18760A3EEEE36EB5D56'
    'OmniPadVirtualKeyboardUmdf.inf' = 'DA625B665866FB216DB20FA3909DFBEC8D6B6D2E3CF45A76C651E5B5486B94EB'
    'OmniPadVirtualKeyboardUmdf.cat' = '1020F1022B4285FC2CFA505316B7ED0831F40A3B934C58F36E1C08EE07FBF98C'
    'OmniPadLocalUmdfDevelopment.cer' = '04794A713B9B891AC0142834EDE9453AB960D53D3162BC428BACD2998D123081'
}

if (-not $TrustBundledCertificate) {
    throw 'Bundled UMDF installation requires -TrustBundledCertificate after the exact trust and device scope is shown.'
}
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this installer from an elevated PowerShell window.'
}
if ([Environment]::OSVersion.Version.Build -lt 22000 -or -not [Environment]::Is64BitOperatingSystem) {
    throw 'The bundled UMDF keyboard requires 64-bit Windows 11 build 22000 or newer.'
}

foreach ($entry in $expectedHashes.GetEnumerator()) {
    $path = Join-Path $package $entry.Key
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Bundled package file is missing: $path"
    }
    $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    if ($actual -ne $entry.Value) {
        throw "Bundled package hash mismatch: $($entry.Key)"
    }
}

$certificatePath = Join-Path $package 'OmniPadLocalUmdfDevelopment.cer'
$catalogPath = Join-Path $package 'OmniPadVirtualKeyboardUmdf.cat'
$infPath = Join-Path $package 'OmniPadVirtualKeyboardUmdf.inf'
$certificate = Get-PfxCertificate -FilePath $certificatePath
if ($certificate.Thumbprint -ne $expectedThumbprint -or $certificate.Subject -ne $certificateSubject) {
    throw 'Bundled UMDF certificate identity does not match the pinned OmniPad signer.'
}
$catalogSignature = Get-AuthenticodeSignature -LiteralPath $catalogPath
if (-not $catalogSignature.SignerCertificate -or
    $catalogSignature.SignerCertificate.Thumbprint -ne $expectedThumbprint) {
    throw 'Bundled UMDF catalog is not signed by the pinned OmniPad signer.'
}

$addedStores = [Collections.Generic.List[string]]::new()
try {
    foreach ($store in @('Root', 'TrustedPublisher')) {
        $certificateStore = "Cert:\LocalMachine\$store"
        if (-not (Test-Path -LiteralPath "$certificateStore\$expectedThumbprint")) {
            Import-Certificate -FilePath $certificatePath -CertStoreLocation $certificateStore | Out-Null
            $addedStores.Add($store)
        }
    }
    $trustedSignature = Get-AuthenticodeSignature -LiteralPath $catalogPath
    if ($trustedSignature.Status -ne 'Valid') {
        throw "Bundled catalog did not become trusted: $($trustedSignature.Status)"
    }
    & (Join-Path $root 'install-driver.ps1') -InfPath $infPath
    if (-not $?) {
        throw 'UMDF device installation failed.'
    }
    Write-Host "Trusted only $certificateSubject ($expectedThumbprint)." -ForegroundColor Yellow
    Write-Host "Installed only $hardwareId from the pinned bundled package." -ForegroundColor Green
} catch {
    $device = Get-PnpDevice -Class HIDClass -ErrorAction SilentlyContinue |
        Where-Object { $_.FriendlyName -eq 'OmniPad Virtual Keyboard Port (UMDF 2)' } |
        Where-Object {
        $ids = (Get-PnpDeviceProperty -InstanceId $_.InstanceId `
            -KeyName 'DEVPKEY_Device_HardwareIds' -ErrorAction SilentlyContinue).Data
        $ids -contains $hardwareId
    } |
        Select-Object -First 1
    if (-not $device) {
        foreach ($store in $addedStores) {
            $path = "Cert:\LocalMachine\$store\$expectedThumbprint"
            if (Test-Path -LiteralPath $path) {
                Remove-Item -LiteralPath $path -Force
            }
        }
    }
    throw
}
