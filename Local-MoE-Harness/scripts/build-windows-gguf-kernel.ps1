param(
    [switch]$KeepBuildTree
)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ConfigPath = Join-Path $Root "config\windows-gguf-prebuilt.json"
$RequirementsPath = Join-Path $Root "config\windows-gguf-build-requirements.txt"
$FtPython = Join-Path $Root ".venvs\freetoken\Scripts\python.exe"
$UvExe = Join-Path $Root "tools\uv\uv.exe"
$BuilderRoot = Join-Path $Root "tools\gguf-builder"
$PackageRoot = Join-Path $BuilderRoot "cuda-packages"
$CudaHome = Join-Path $BuilderRoot "cuda"
$TorchExtensions = Join-Path $BuilderRoot "torch-extensions"
$VendorDir = Join-Path $Root "vendor\windows"
$LogDir = Join-Path $Root "logs"
$BuildLog = Join-Path $LogDir "windows-gguf-maintainer-build.log"
$BuildStdout = Join-Path $BuilderRoot "gguf-build.stdout.log"
$BuildStderr = Join-Path $BuilderRoot "gguf-build.stderr.log"
$BuildProbe = Join-Path $BuilderRoot "invoke-gguf-build.py"

if (-not $IsWindows -and $env:OS -ne "Windows_NT") {
    throw "The GGUF prebuilt kernel must be built on Windows."
}
if (-not (Test-Path -LiteralPath $FtPython)) {
    throw "Project-local FreeToken environment is missing. Run Setup.bat first."
}
if (-not (Test-Path -LiteralPath $UvExe)) {
    throw "Project-local uv is missing. Run Setup.bat first."
}

$Config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json

function Import-VsDevEnvironment {
    $VsWhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
    if (-not (Test-Path -LiteralPath $VsWhere)) {
        throw "Maintainer build requires Visual Studio 2022 Build Tools with MSVC. vswhere.exe was not found."
    }
    # CUDA 13.0's supported Windows host-compiler range includes VS 2022/MSVC 193x.
    # Pin the maintainer build to that generation rather than silently selecting a future VS.
    $VsInstall = (& $VsWhere -latest -version "[17.0,18.0)" -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath | Select-Object -First 1)
    if (-not $VsInstall) {
        throw "Maintainer build requires Visual Studio 2022 Build Tools with the x64 C++ toolset."
    }
    $VsDevCmd = Join-Path $VsInstall "Common7\Tools\VsDevCmd.bat"
    if (-not (Test-Path -LiteralPath $VsDevCmd)) {
        throw "VsDevCmd.bat was not found under $VsInstall"
    }

    $Dump = & $env:ComSpec /d /s /c "`"$VsDevCmd`" -no_logo -arch=x64 -host_arch=x64 && set"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to activate the maintainer MSVC environment."
    }
    foreach ($Line in $Dump) {
        if ($Line -match "^([^=]+)=(.*)$") {
            Set-Item -Path ("Env:" + $Matches[1]) -Value $Matches[2]
        }
    }
    $Cl = Get-Command cl.exe -ErrorAction SilentlyContinue
    if (-not $Cl) {
        throw "MSVC activation completed but cl.exe is still unavailable."
    }
    return [ordered]@{
        installation_path = $VsInstall
        cl_path = $Cl.Source
    }
}

function Merge-Directory([string]$Source, [string]$Destination) {
    if (-not (Test-Path -LiteralPath $Source)) { return }
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    Get-ChildItem -LiteralPath $Source -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $Destination -Recurse -Force
    }
}

Write-Host "[GGUF Build] This is a maintainer-only release build."
Write-Host "[GGUF Build] Public users will NOT need MSVC, Ninja, or a CUDA toolkit."
$Msvc = Import-VsDevEnvironment

New-Item -ItemType Directory -Force -Path $BuilderRoot,$PackageRoot,$CudaHome,$TorchExtensions,$VendorDir,$LogDir | Out-Null
if (-not $KeepBuildTree) {
    Get-ChildItem -LiteralPath $PackageRoot -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
    Get-ChildItem -LiteralPath $CudaHome -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
    Get-ChildItem -LiteralPath $TorchExtensions -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
}
foreach ($OldLog in @($BuildLog,$BuildStdout,$BuildStderr,$BuildProbe)) {
    Remove-Item -LiteralPath $OldLog -Force -ErrorAction SilentlyContinue
}

$env:UV_CACHE_DIR = Join-Path $Root ".cache\uv"
$env:UV_PYTHON_NO_REGISTRY = "1"
$env:PIP_CACHE_DIR = Join-Path $Root ".cache\pip"
$env:TEMP = Join-Path $Root ".tmp"
$env:TMP = Join-Path $Root ".tmp"
$env:TORCH_EXTENSIONS_DIR = $TorchExtensions
$env:DISTUTILS_USE_SDK = "1"
$env:MAX_JOBS = "1"

Write-Host "[GGUF Build] Installing hash-pinned CUDA 13 compiler components and Ninja into tools\gguf-builder..."
& $UvExe pip install --target $PackageRoot --no-deps --require-hashes -r $RequirementsPath
if ($LASTEXITCODE -ne 0) {
    throw "Pinned maintainer build-package installation failed."
}

$NvidiaRoot = Join-Path $PackageRoot "nvidia"
if (-not (Test-Path -LiteralPath $NvidiaRoot)) {
    throw "Pinned NVIDIA packages did not create the expected nvidia package root."
}

$CudaPackageRoot = Join-Path $NvidiaRoot "cu13"
if (-not (Test-Path -LiteralPath $CudaPackageRoot)) {
    throw "Pinned NVIDIA packages did not create the expected nvidia\cu13 CUDA root."
}
Merge-Directory $CudaPackageRoot $CudaHome

$NvvmBin = Join-Path $CudaHome "nvvm\bin"
New-Item -ItemType Directory -Force -Path $NvvmBin | Out-Null
$CiccCandidate = Join-Path $CudaHome "bin\cicc.exe"
$NvvmCicc = Join-Path $NvvmBin "cicc.exe"
if ((Test-Path -LiteralPath $CiccCandidate) -and -not (Test-Path -LiteralPath $NvvmCicc)) {
    Copy-Item -LiteralPath $CiccCandidate -Destination $NvvmCicc -Force
}

$Nvcc = Join-Path $CudaHome "bin\nvcc.exe"
$CudaRuntimeHeader = Join-Path $CudaHome "include\cuda_runtime.h"
$CudartLib = Join-Path $CudaHome "lib\x64\cudart.lib"
$LibDevice = Join-Path $CudaHome "nvvm\libdevice\libdevice.10.bc"
foreach ($Required in @($Nvcc, $CudaRuntimeHeader, $CudartLib, $LibDevice, $NvvmCicc)) {
    if (-not (Test-Path -LiteralPath $Required)) {
        throw "The project-local CUDA build tree is incomplete; missing $Required"
    }
}

$TorchCompiledAutograd = Join-Path $Root ".venvs\freetoken\Lib\site-packages\torch\include\torch\csrc\dynamo\compiled_autograd.h"
if (Test-Path -LiteralPath $TorchCompiledAutograd) {
    $AutogradContent = [System.IO.File]::ReadAllText($TorchCompiledAutograd)
    if ($AutogradContent.Contains("#if defined(_WIN32) && (defined(USE_CUDA) || defined(USE_ROCM))")) {
        $AutogradContent = $AutogradContent.Replace("#if defined(_WIN32) && (defined(USE_CUDA) || defined(USE_ROCM))", "#if defined(_WIN32)")
        [System.IO.File]::WriteAllText($TorchCompiledAutograd, $AutogradContent, [System.Text.Encoding]::UTF8)
    }
}

$NinjaCandidates = @(Get-ChildItem -LiteralPath $PackageRoot -Recurse -File -Filter "ninja.exe" -ErrorAction SilentlyContinue)
if ($NinjaCandidates.Count -lt 1) {
    throw "The pinned Ninja wheel did not provide ninja.exe under tools\gguf-builder."
}
$Ninja = $NinjaCandidates | Sort-Object FullName | Select-Object -First 1
$NinjaVersion = (& $Ninja.FullName --version | Select-Object -First 1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $NinjaVersion -notmatch "^1\.13\.2") {
    throw "Project-local Ninja version mismatch: expected 1.13.2, got '$NinjaVersion'."
}

$env:CUDA_HOME = $CudaHome
$env:CUDA_PATH = $CudaHome
$env:CUDA_PATH_V13_0 = $CudaHome
$env:PATH = "$($Ninja.DirectoryName);$(Join-Path $CudaHome 'bin');$env:PATH"
$env:TORCH_CUDA_ARCH_LIST = [string]$Config.build_arch_list

$ResolvedNinja = (Get-Command ninja.exe -ErrorAction SilentlyContinue)
if (-not $ResolvedNinja -or $ResolvedNinja.Source -ne $Ninja.FullName) {
    throw "Project-local Ninja was not selected first on PATH. Resolved: $($ResolvedNinja.Source)"
}

$RuntimeInfoRaw = & $FtPython -c "import importlib.metadata as m, json, sys, torch; print(json.dumps({'python': f'{sys.version_info.major}.{sys.version_info.minor}', 'freetoken': m.version('freetoken'), 'torch': str(torch.__version__), 'torch_cuda': str(torch.version.cuda)}))"
if ($LASTEXITCODE -ne 0) { throw "Could not inspect the project-local FreeToken environment." }
$RuntimeInfo = $RuntimeInfoRaw | Select-Object -Last 1 | ConvertFrom-Json
if ($RuntimeInfo.python -ne [string]$Config.python_major_minor) {
    throw "Python mismatch: expected $($Config.python_major_minor), got $($RuntimeInfo.python)"
}
if ($RuntimeInfo.freetoken -ne [string]$Config.freetoken_version) {
    throw "FreeToken mismatch: expected $($Config.freetoken_version), got $($RuntimeInfo.freetoken)"
}
if ($RuntimeInfo.torch -ne [string]$Config.torch_version) {
    throw "Torch mismatch: expected $($Config.torch_version), got $($RuntimeInfo.torch)"
}
if ($RuntimeInfo.torch_cuda -ne "13.0") {
    throw "Torch CUDA ABI mismatch: expected 13.0, got $($RuntimeInfo.torch_cuda)"
}

$NvccVersion = (& $Nvcc --version) -join "`n"
if ($LASTEXITCODE -ne 0 -or $NvccVersion -notmatch "release 13\.0") {
    throw "Project-local nvcc is not CUDA 13.0."
}
$ClBanner = (& cmd.exe /d /c "cl.exe 2>&1" | Select-Object -First 1 | Out-String).Trim()

@'
import freetoken.kernel.gguf as g
print(g._module().__file__)
'@ | Set-Content -LiteralPath $BuildProbe -Encoding UTF8

Write-Host "[GGUF Build] Building FreeToken's official GGUF torch extension..."
Write-Host "[GGUF Build] Compiler output will be preserved at $BuildLog"
$BuildProcess = Start-Process -FilePath $FtPython -ArgumentList @("`"$BuildProbe`"") -WorkingDirectory $Root -NoNewWindow -Wait -PassThru -RedirectStandardOutput $BuildStdout -RedirectStandardError $BuildStderr
$StdoutLines = @()
$StderrLines = @()
if (Test-Path -LiteralPath $BuildStdout) { $StdoutLines = @(Get-Content -LiteralPath $BuildStdout -ErrorAction SilentlyContinue) }
if (Test-Path -LiteralPath $BuildStderr) { $StderrLines = @(Get-Content -LiteralPath $BuildStderr -ErrorAction SilentlyContinue) }
@(
    "=== Local MoE Harness Windows GGUF maintainer build ==="
    "UTC: $([DateTimeOffset]::UtcNow.ToString('o'))"
    "FreeToken: $($RuntimeInfo.freetoken)"
    "Torch: $($RuntimeInfo.torch)"
    "Torch CUDA ABI: $($RuntimeInfo.torch_cuda)"
    "MSVC: $ClBanner"
    "MSVC path: $($Msvc.cl_path)"
    "NVCC: $Nvcc"
    "Ninja: $($Ninja.FullName) ($NinjaVersion)"
    "CUDA_HOME: $CudaHome"
    "TORCH_CUDA_ARCH_LIST: $env:TORCH_CUDA_ARCH_LIST"
    ""
    "=== STDOUT ==="
) + $StdoutLines + @(
    ""
    "=== STDERR ==="
) + $StderrLines | Set-Content -LiteralPath $BuildLog -Encoding UTF8

if ($BuildProcess.ExitCode -ne 0) {
    Write-Host ""
    Write-Host "[GGUF Build] FreeToken GGUF extension build failed with exit code $($BuildProcess.ExitCode)." -ForegroundColor Red
    Write-Host "[GGUF Build] Full compiler output: $BuildLog" -ForegroundColor Yellow
    if ($StderrLines.Count -gt 0) {
        Write-Host "[GGUF Build] Last compiler stderr lines:" -ForegroundColor Yellow
        $StderrLines | Select-Object -Last 80 | ForEach-Object { Write-Host $_ }
    }
    throw "FreeToken GGUF extension build failed. See $BuildLog for the first causal compiler diagnostic."
}

$ModuleOutput = $StdoutLines
$ModulePath = ($ModuleOutput | Where-Object { $_ -match "\.pyd\s*$" } | Select-Object -Last 1)
if (-not $ModulePath) {
    throw "Build completed without reporting a .pyd output path. See $BuildLog"
}
$ModulePath = $ModulePath.Trim()
if (-not (Test-Path -LiteralPath $ModulePath)) {
    throw "Built GGUF extension was not found at $ModulePath"
}

$ArtifactPath = Join-Path $Root ([string]$Config.artifact_path)
Copy-Item -LiteralPath $ModulePath -Destination $ArtifactPath -Force
$ArtifactHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $ArtifactPath).Hash.ToLowerInvariant()

$ManifestPath = Join-Path $Root ([string]$Config.artifact_manifest_path)
$Manifest = [ordered]@{
    schema_version = 1
    artifact = Split-Path -Leaf $ArtifactPath
    sha256 = $ArtifactHash
    module_name = [string]$Config.module_name
    python_major_minor = [string]$Config.python_major_minor
    freetoken_version = [string]$Config.freetoken_version
    torch_version = [string]$Config.torch_version
    torch_cuda = [string]$RuntimeInfo.torch_cuda
    cuda_nvcc_version = "13.0.48"
    cuda_nvvm_version = "13.0.48"
    ninja_version = $NinjaVersion
    torch_cuda_arch_list = [string]$Config.build_arch_list
    maintainer_msvc = $ClBanner
    maintainer_msvc_installation = [string]$Msvc.installation_path
    source = "FreeToken official Windows wheel GGUF JIT source"
    public_runtime_requires_compiler = $false
    built_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
}
$Utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText($ManifestPath, (($Manifest | ConvertTo-Json -Depth 5) + "`r`n"), $Utf8NoBom)

Write-Host ""
Write-Host "[GGUF Build] READY"
Write-Host "  Artifact: $ArtifactPath"
Write-Host "  SHA-256:  $ArtifactHash"
Write-Host "  Manifest: $ManifestPath"
Write-Host "  Build log: $BuildLog"
Write-Host ""
Write-Host "Next: close this maintainer shell and validate Gemma from an ordinary PowerShell."
Write-Host "The ordinary public runtime must succeed without cl.exe, ninja.exe, nvcc.exe, or a CUDA toolkit on PATH."
