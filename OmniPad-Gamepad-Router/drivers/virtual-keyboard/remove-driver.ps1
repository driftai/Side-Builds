$ErrorActionPreference = 'Continue'

Write-Host 'OmniPad Virtual Keyboard HID removal' -ForegroundColor Cyan
$devconCommand = Get-Command devcon.exe -ErrorAction SilentlyContinue
$devcon = if ($devconCommand) { $devconCommand.Source } else {
    Get-ChildItem "$env:ProgramFiles(x86)\Windows Kits\10\Tools" -Filter devcon.exe -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match '\\x64\\' } |
        Sort-Object FullName -Descending |
        Select-Object -ExpandProperty FullName -First 1
}
if (-not $devcon) { Write-Error 'devcon.exe not found. Install the matching WDK.'; exit 1 }

& $devcon remove "Root\OmniPadVirtualKeyboard"
$exit = $LASTEXITCODE
if ($exit -eq 0) {
    Write-Host 'OmniPad virtual keyboard device removed.' -ForegroundColor Green
} else {
    Write-Warning "devcon remove returned exit code $exit. If the device is already absent this is harmless."
}
