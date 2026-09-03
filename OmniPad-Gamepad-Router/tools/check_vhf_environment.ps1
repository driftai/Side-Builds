$ErrorActionPreference = 'Continue'
Write-Host "OmniPad Virtual Keyboard HID environment check" -ForegroundColor Cyan
Write-Host "----------------------------------------------"

$root = Split-Path -Parent $PSScriptRoot
$driverDir = Join-Path $root "drivers\virtual-keyboard"
$vswhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
$kitRoot = Join-Path ${env:ProgramFiles(x86)} "Windows Kits\10"

$vsInstall = $null
$msbuild = $null
if (Test-Path $vswhere) {
    Write-Host "[OK] Visual Studio Installer / vswhere: $vswhere"
    $vsInstall = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
} else {
    Write-Host "[--] Visual Studio Installer / vswhere not found"
}
if ($vsInstall) {
    Write-Host "[OK] Compatible Visual Studio: $vsInstall"
    $msbuild64 = Join-Path $vsInstall "MSBuild\Current\Bin\amd64\MSBuild.exe"
    $msbuild32 = Join-Path $vsInstall "MSBuild\Current\Bin\MSBuild.exe"
    $msbuild = if (Test-Path $msbuild64) { $msbuild64 } else { $msbuild32 }
} else {
    Write-Host "[--] Compatible Visual Studio with C++ tools not found"
}
if ($msbuild -and (Test-Path $msbuild)) { Write-Host "[OK] MSBuild: $msbuild" } else { Write-Host "[--] MSBuild not found" }

$kitParts = @('bin', 'Include', 'Lib', 'build')
$missingKitParts = $kitParts | Where-Object { -not (Test-Path (Join-Path $kitRoot $_)) }
$vhfLibrary = Get-ChildItem (Join-Path $kitRoot 'Lib') -Filter VhfKm.lib -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match '\\km\\x64\\' } |
    Select-Object -First 1
$missingKitRequirements = @($missingKitParts)
if (-not $vhfLibrary) { $missingKitRequirements += 'VhfKm.lib' }
if ($missingKitParts.Count -eq 0 -and $vhfLibrary) {
    Write-Host "[OK] Windows SDK/WDK with x64 VhfKm.lib: $($vhfLibrary.FullName)"
} else {
    Write-Host "[--] Complete Windows SDK/WDK not found (missing: $($missingKitRequirements -join ', '))"
}

$driverToolset = if ($vsInstall) {
    Join-Path $vsInstall 'MSBuild\Microsoft\VC\v170\Platforms\x64\PlatformToolsets\WindowsKernelModeDriver10.0'
}
if ($driverToolset -and (Test-Path $driverToolset)) {
    Write-Host "[OK] WDK MSBuild driver toolset: $driverToolset"
} else {
    Write-Host "[--] WDK MSBuild driver toolset not found"
}

$devcon = Get-Command devcon.exe -ErrorAction SilentlyContinue
if (-not $devcon) {
    $devcon = Get-ChildItem (Join-Path $kitRoot 'Tools') -Filter devcon.exe -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match '\\x64\\' } | Select-Object -First 1
}
$devconPath = if ($devcon -is [System.Management.Automation.CommandInfo]) { $devcon.Source } else { $devcon.FullName }
if ($devconPath) { Write-Host "[OK] DevCon: $devconPath" } else { Write-Host "[--] DevCon x64 not found" }

$required = @(
    "OmniPadVirtualKeyboard.c",
    "OmniPadVirtualKeyboard.h",
    "OmniPadVirtualKeyboard.inf",
    "OmniPadVirtualKeyboard.vcxproj"
)
foreach ($name in $required) {
    if (Test-Path (Join-Path $driverDir $name)) { Write-Host "[OK] Driver source: $name" } else { Write-Host "[!!] Missing driver source: $name" }
}

$bcdOutput = & bcdedit /enum 2>&1
$bcdExit = $LASTEXITCODE
$testSigning = $bcdOutput | Select-String -Pattern 'testsigning'
if ($bcdExit -ne 0) {
    Write-Host "[??] Windows test-signing status unavailable (BCD access denied or unreadable)"
} elseif ($testSigning -and ($testSigning.ToString() -match 'Yes')) {
    Write-Host "[OK] Windows test-signing appears enabled" -ForegroundColor Yellow
} else {
    Write-Host "[--] Windows test-signing is not enabled (normal on production systems)"
}

Write-Host ""
Write-Host "Next: build the driver with the matching Visual Studio + WDK toolchain, then install it only on a development/test machine."
