$ErrorActionPreference = 'Continue'

Write-Host 'OmniPad Virtual Keyboard HID removal' -ForegroundColor Cyan
$devconCandidates = @(
    "$env:ProgramFiles(x86)\Windows Kits\10\Tools\10.0.26100.0\x64\devcon.exe",
    "$env:ProgramFiles(x86)\Windows Kits\10\Tools\10.0.26100.0\arm64\devcon.exe"
)
$devcon = $devconCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $devcon) { Write-Error 'devcon.exe not found. Install the matching WDK.'; exit 1 }

& $devcon remove "Root\OmniPadVirtualKeyboard"
$exit = $LASTEXITCODE
if ($exit -eq 0) {
    Write-Host 'OmniPad virtual keyboard device removed.' -ForegroundColor Green
} else {
    Write-Warning "devcon remove returned exit code $exit. If the device is already absent this is harmless."
}
