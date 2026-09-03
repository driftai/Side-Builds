$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host 'OmniPad Virtual Keyboard HID installer' -ForegroundColor Cyan
Write-Host 'This installer only accepts a complete, validly signed build package.'
Write-Host ''

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Driver installation requires an elevated PowerShell prompt.'
}

$packageCandidates = @(
    (Join-Path $root 'x64\Release\OmniPadVirtualKeyboard'),
    (Join-Path $root 'x64\Debug\OmniPadVirtualKeyboard')
)
$package = $packageCandidates |
    Where-Object {
        (Test-Path (Join-Path $_ 'OmniPadVirtualKeyboard.inf')) -and
        (Test-Path (Join-Path $_ 'OmniPadVirtualKeyboard.sys')) -and
        (Test-Path (Join-Path $_ 'omnipadvirtualkeyboard.cat'))
    } |
    Select-Object -First 1

if (-not $package) {
    throw 'A complete x64 driver package was not found. Run build-driver.ps1 first.'
}

$inf = Join-Path $package 'OmniPadVirtualKeyboard.inf'
$sys = Join-Path $package 'OmniPadVirtualKeyboard.sys'
$cat = Join-Path $package 'omnipadvirtualkeyboard.cat'

foreach ($file in @($sys, $cat)) {
    $signature = Get-AuthenticodeSignature -FilePath $file
    if ($signature.Status -ne 'Valid') {
        throw "Refusing to install $file because its signature status is $($signature.Status). Sign and trust the complete package first."
    }
}

$devconCommand = Get-Command devcon.exe -ErrorAction SilentlyContinue
$devcon = if ($devconCommand) { $devconCommand.Source } else {
    Get-ChildItem "$env:ProgramFiles(x86)\Windows Kits\10\Tools" -Filter devcon.exe -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match '\\x64\\' } |
        Sort-Object FullName -Descending |
        Select-Object -ExpandProperty FullName -First 1
}

if (-not $devcon) {
    throw 'devcon.exe was not found. Install the matching Windows Driver Kit (WDK), then run this script from an elevated PowerShell prompt.'
}

Write-Host 'Enabling Windows test signing is intentionally NOT automated.' -ForegroundColor Yellow
Write-Host 'Secure Boot/Test Mode, certificate trust, BCD changes, and reboot remain manual safety checkpoints.'
Write-Host ''
Write-Host "Installing: $inf" -ForegroundColor Green
& $devcon install $inf Root\OmniPadVirtualKeyboard
if ($LASTEXITCODE -ne 0) { throw "devcon install failed with exit code $LASTEXITCODE" }

Write-Host 'Driver/device install request completed.' -ForegroundColor Green
Write-Host 'Verify Device Manager shows OmniPad Virtual Keyboard / HID keyboard entries before selecting the VHF backend in OmniPad.'
