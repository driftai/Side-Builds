$ErrorActionPreference = 'SilentlyContinue'
Write-Host "OmniPad Virtual Keyboard HID environment check" -ForegroundColor Cyan
Write-Host "----------------------------------------------"

$root = Split-Path -Parent $PSScriptRoot
$driverDir = Join-Path $root "drivers\virtual-keyboard"
$vswhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
$devcon = Get-Command devcon.exe -ErrorAction SilentlyContinue
$msbuild = Get-Command msbuild.exe -ErrorAction SilentlyContinue

if (Test-Path $vswhere) { Write-Host "[OK] Visual Studio Installer / vswhere: $vswhere" } else { Write-Host "[--] vswhere.exe not found" }
if ($msbuild) { Write-Host "[OK] msbuild.exe: $($msbuild.Source)" } else { Write-Host "[--] msbuild.exe not on PATH" }
if ($devcon) { Write-Host "[OK] devcon.exe: $($devcon.Source)" } else { Write-Host "[--] devcon.exe not on PATH" }

$kits = Get-ChildItem "C:\Program Files (x86)\Windows Kits\10" -Directory -ErrorAction SilentlyContinue
if ($kits) { Write-Host "[OK] Windows Kits installation found" } else { Write-Host "[--] Windows Kits installation not found" }

$required = @(
    "OmniPadVirtualKeyboard.c",
    "OmniPadVirtualKeyboard.h",
    "OmniPadVirtualKeyboard.inf",
    "OmniPadVirtualKeyboard.vcxproj"
)
foreach ($name in $required) {
    if (Test-Path (Join-Path $driverDir $name)) { Write-Host "[OK] Driver source: $name" } else { Write-Host "[!!] Missing driver source: $name" }
}

$testSigning = (& bcdedit /enum '{current}' 2>$null | Select-String -Pattern 'testsigning')
if ($testSigning -and ($testSigning.ToString() -match 'Yes')) {
    Write-Host "[OK] Windows test-signing appears enabled" -ForegroundColor Yellow
} else {
    Write-Host "[--] Windows test-signing is not enabled (normal on production systems)"
}

Write-Host ""
Write-Host "Next: build the driver with the matching Visual Studio + WDK toolchain, then install it only on a development/test machine."
