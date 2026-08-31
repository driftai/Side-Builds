$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$inf = Join-Path $root 'OmniPadVirtualKeyboard.inf'

if (-not (Test-Path $inf)) { throw "INF not found: $inf" }

Write-Host 'OmniPad Virtual Keyboard HID installer' -ForegroundColor Cyan
Write-Host 'This is a development driver. A test-signed driver requires Windows Test Mode.'
Write-Host ''

$devconCandidates = @(
    "$env:ProgramFiles(x86)\Windows Kits\10\Tools\10.0.26100.0\x64\devcon.exe",
    "$env:ProgramFiles(x86)\Windows Kits\10\Tools\10.0.26100.0\arm64\devcon.exe"
)
$devcon = $devconCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $devcon) {
    throw 'devcon.exe was not found. Install the matching Windows Driver Kit (WDK), then run this script from an elevated PowerShell prompt.'
}

Write-Host 'Enabling Windows test signing is intentionally NOT automated.' -ForegroundColor Yellow
Write-Host 'Use an elevated prompt and reboot only when you deliberately choose development test mode:'
Write-Host '  bcdedit /set testsigning on'
Write-Host ''
Write-Host "Installing: $inf" -ForegroundColor Green
& $devcon install $inf Root\OmniPadVirtualKeyboard
if ($LASTEXITCODE -ne 0) { throw "devcon install failed with exit code $LASTEXITCODE" }

Write-Host 'Driver/device install request completed.' -ForegroundColor Green
Write-Host 'Verify Device Manager shows OmniPad Virtual Keyboard / HID keyboard entries before selecting the VHF backend in OmniPad.'
