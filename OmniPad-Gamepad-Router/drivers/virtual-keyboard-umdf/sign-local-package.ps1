param(
    [switch]$TrustLocalCertificate,
    [switch]$InstallAfterSigning,
    [string]$PackageDirectory = ""
)

$ErrorActionPreference = 'Stop'
$subject = 'CN=OmniPad Local UMDF Development'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not $TrustLocalCertificate) {
    throw 'This action creates and trusts a machine-local driver signing certificate. Re-run with -TrustLocalCertificate only after reviewing that trust change.'
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this signing step from an elevated PowerShell window.'
}

if (-not $PackageDirectory) {
    $package = Get-ChildItem -LiteralPath $root -Recurse -Filter 'OmniPadVirtualKeyboardUmdf.inf' -File |
        Where-Object { $_.FullName -match '\\x64\\Debug\\OmniPadVirtualKeyboardUmdf\\' } |
        Select-Object -First 1
    if (-not $package) {
        throw 'Packaged INF not found. Run build-driver.ps1 first.'
    }
    $PackageDirectory = $package.DirectoryName
}

$PackageDirectory = (Resolve-Path -LiteralPath $PackageDirectory).Path
$catalog = Join-Path $PackageDirectory 'OmniPadVirtualKeyboardUmdf.cat'
if (-not (Test-Path -LiteralPath $catalog)) {
    throw "Catalog not found: $catalog"
}

$certificate = Get-ChildItem -LiteralPath 'Cert:\LocalMachine\My' |
    Where-Object { $_.Subject -eq $subject -and $_.HasPrivateKey -and $_.NotAfter -gt (Get-Date).AddDays(30) } |
    Sort-Object NotAfter -Descending |
    Select-Object -First 1

if (-not $certificate) {
    $certificate = New-SelfSignedCertificate `
        -Subject $subject `
        -Type CodeSigningCert `
        -KeyAlgorithm RSA `
        -KeyLength 3072 `
        -HashAlgorithm SHA256 `
        -KeyUsage DigitalSignature `
        -KeyExportPolicy NonExportable `
        -CertStoreLocation 'Cert:\LocalMachine\My' `
        -NotAfter (Get-Date).AddYears(2)
}

$publicCertificate = Join-Path $PackageDirectory 'OmniPadLocalUmdfDevelopment.cer'
Export-Certificate -Cert $certificate -FilePath $publicCertificate -Force | Out-Null

foreach ($store in @('Cert:\LocalMachine\Root', 'Cert:\LocalMachine\TrustedPublisher')) {
    $trusted = Get-ChildItem -LiteralPath $store | Where-Object { $_.Thumbprint -eq $certificate.Thumbprint }
    if (-not $trusted) {
        Import-Certificate -FilePath $publicCertificate -CertStoreLocation $store | Out-Null
    }
}

$kitsBin = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\bin'
$signTool = Get-ChildItem -LiteralPath $kitsBin -Recurse -Filter 'signtool.exe' -File |
    Where-Object { $_.FullName -match '\\x64\\signtool.exe$' } |
    Sort-Object FullName -Descending |
    Select-Object -First 1 -ExpandProperty FullName
if (-not $signTool) {
    throw 'x64 signtool.exe was not found in the Windows Kits.'
}

& $signTool sign /fd SHA256 /sm /s My /sha1 $certificate.Thumbprint $catalog
if ($LASTEXITCODE -ne 0) {
    throw "SignTool failed with exit code $LASTEXITCODE"
}

$signature = Get-AuthenticodeSignature -LiteralPath $catalog
if ($signature.Status -ne 'Valid') {
    throw "Catalog signature verification failed: $($signature.Status)"
}

Write-Host "Signed catalog with local certificate $($certificate.Thumbprint)." -ForegroundColor Green
Write-Host 'Certificate trust changed; boot mode, BCD, and Secure Boot were not changed.' -ForegroundColor Yellow

if ($InstallAfterSigning) {
    & (Join-Path $root 'install-driver.ps1') -InfPath (Join-Path $PackageDirectory 'OmniPadVirtualKeyboardUmdf.inf')
}
