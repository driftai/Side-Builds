$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$project = Join-Path $root 'OmniPadVirtualKeyboard.vcxproj'

Write-Host '== OmniPad Virtual Keyboard HID Driver Build ==' -ForegroundColor Cyan

if (-not (Test-Path $project)) {
    throw "Driver project not found: $project"
}

$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
if (-not (Test-Path $vswhere)) {
    throw 'Visual Studio vswhere.exe was not found. Install Visual Studio 2022 with the WDK workload.'
}

$vs = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $vs) {
    throw 'A compatible Visual Studio installation was not found.'
}

$msbuild64 = Join-Path $vs 'MSBuild\Current\Bin\amd64\MSBuild.exe'
$msbuild32 = Join-Path $vs 'MSBuild\Current\Bin\MSBuild.exe'
$msbuild = if (Test-Path $msbuild64) { $msbuild64 } else { $msbuild32 }
if (-not (Test-Path $msbuild)) {
    throw "MSBuild not found at $msbuild"
}

& $msbuild $project /m /p:Configuration=Debug /p:Platform=x64 /p:SignMode=Off
if ($LASTEXITCODE -ne 0) { throw "Driver build failed with exit code $LASTEXITCODE" }

Get-ChildItem $root -Recurse -File |
    Where-Object { $_.Extension -in '.sys', '.inf', '.cat' } |
    ForEach-Object { Write-Host "  $($_.FullName)" }

Write-Host 'Build completed. Install the generated INF on a test-signed Windows machine.' -ForegroundColor Green
