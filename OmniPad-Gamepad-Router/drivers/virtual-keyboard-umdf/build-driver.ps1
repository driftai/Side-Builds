$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$project = Join-Path $root 'OmniPadVirtualKeyboardUmdf.vcxproj'

Write-Host '== OmniPad UMDF Virtual Keyboard Port Build ==' -ForegroundColor Cyan

$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
if (-not (Test-Path -LiteralPath $vswhere)) {
    throw 'Visual Studio vswhere.exe was not found. Install VS Build Tools 2022 and the WDK.'
}

$vs = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $vs) {
    throw 'A compatible Visual Studio C++ installation was not found.'
}

$msbuild64 = Join-Path $vs 'MSBuild\Current\Bin\amd64\MSBuild.exe'
$msbuild32 = Join-Path $vs 'MSBuild\Current\Bin\MSBuild.exe'
$msbuild = if (Test-Path -LiteralPath $msbuild64) { $msbuild64 } else { $msbuild32 }
if (-not (Test-Path -LiteralPath $msbuild)) {
    throw "MSBuild was not found at $msbuild"
}

& $msbuild $project /m /p:Configuration=Debug /p:Platform=x64 /p:SignMode=Off
if ($LASTEXITCODE -ne 0) {
    throw "UMDF driver build failed with exit code $LASTEXITCODE"
}

Get-ChildItem -LiteralPath $root -Recurse -File |
    Where-Object { $_.Extension -in '.dll', '.inf', '.cat' } |
    ForEach-Object { Write-Host "  $($_.FullName)" }

Write-Host 'Build complete. The package is intentionally unsigned and was not installed.' -ForegroundColor Green
