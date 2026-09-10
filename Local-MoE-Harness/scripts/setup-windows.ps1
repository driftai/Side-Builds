$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ConfigPath = Join-Path $Root "config\windows-runtime.json"
$Config = Get-Content -Raw -Path $ConfigPath | ConvertFrom-Json

function Assert-Hash([string]$Path, [string]$Expected) {
    $Actual = (Get-FileHash -Algorithm SHA256 -Path $Path).Hash.ToLowerInvariant()
    if ($Actual -ne $Expected.ToLowerInvariant()) { throw "SHA-256 mismatch for $Path. Expected $Expected, got $Actual" }
}
function Download-Verified([string]$Url, [string]$Path, [string]$Sha256) {
    if (Test-Path $Path) {
        try { Assert-Hash $Path $Sha256; Write-Host "[Setup] Reusing verified $(Split-Path -Leaf $Path)"; return }
        catch { Remove-Item -Force $Path }
    }
    Write-Host "[Setup] Downloading $Url"
    Invoke-WebRequest -UseBasicParsing -Uri $Url -OutFile $Path
    Assert-Hash $Path $Sha256
}

# A project tree copied from Linux/WSL may contain POSIX virtual environments,
# managed Python builds and compiler/JIT caches. Those artifacts are not portable
# to native Windows. Detect that case before provisioning and remove only
# disposable platform-specific runtime state. Models, config, source, vendor
# artifacts, downloads and user selection state are intentionally preserved.
# Include regular POSIX activation scripts because Windows filesystem copies such
# as Robocopy /XJ can omit the Linux python symlink while preserving bin/activate.
$LinuxRuntimeMarkers = @(
    (Join-Path $Root ".venv\bin\python"),
    (Join-Path $Root ".venvs\freetoken\bin\python"),
    (Join-Path $Root ".venv\bin\activate"),
    (Join-Path $Root ".venvs\freetoken\bin\activate")
)
$WslCopyDetected = $false
foreach ($Marker in $LinuxRuntimeMarkers) {
    if (Test-Path -LiteralPath $Marker) { $WslCopyDetected = $true; break }
}
if ($WslCopyDetected) {
    Write-Host "[Setup] Linux/WSL runtime artifacts detected; rehydrating this copied tree for native Windows."
    $DisposableRuntimePaths = @(
        ".venv",
        ".venvs\freetoken",
        "tools\python",
        "tools\uv",
        ".cache\uv",
        ".cache\pip",
        ".cache\torch",
        ".cache\triton",
        ".cache\flashinfer",
        ".cache\torch_extensions",
        ".cache\windows",
        ".tmp"
    )
    foreach ($Relative in $DisposableRuntimePaths) {
        $Path = Join-Path $Root $Relative
        if (Test-Path -LiteralPath $Path) {
            Remove-Item -LiteralPath $Path -Recurse -Force
        }
    }
    foreach ($PidFile in @("state\harness.pid", "state\freetoken.pid")) {
        Remove-Item -LiteralPath (Join-Path $Root $PidFile) -Force -ErrorAction SilentlyContinue
    }
}

$Dirs = @(".cache", ".cache\windows\AppData", ".cache\windows\LocalAppData", ".tmp", ".venvs", "logs", "models", "models\hf_cache", "state", "tools", "tools\downloads", "tools\python", "tools\uv")
foreach ($Relative in $Dirs) { New-Item -ItemType Directory -Force -Path (Join-Path $Root $Relative) | Out-Null }

# uv/Python are intentionally portable: cache, managed interpreter, launcher and
# even registry discovery/registration are kept away from the user's global profile.
$env:UV_CACHE_DIR = Join-Path $Root ".cache\uv"
$env:UV_PYTHON_INSTALL_DIR = Join-Path $Root "tools\python"
$env:UV_PYTHON_BIN_DIR = Join-Path $Root "tools\python\bin"
$env:UV_PYTHON_INSTALL_BIN = "1"
$env:UV_PYTHON_NO_REGISTRY = "1"
$env:PIP_CACHE_DIR = Join-Path $Root ".cache\pip"
$env:HF_HOME = Join-Path $Root "models\hf_cache"
$env:HUGGINGFACE_HUB_CACHE = Join-Path $Root "models\hf_cache\hub"
$env:XDG_CACHE_HOME = Join-Path $Root ".cache"
$env:TORCH_HOME = Join-Path $Root ".cache\torch"
$env:TRITON_CACHE_DIR = Join-Path $Root ".cache\triton"
$env:FLASHINFER_WORKSPACE_DIR = Join-Path $Root ".cache\flashinfer"
$env:TORCH_EXTENSIONS_DIR = Join-Path $Root ".cache\torch_extensions"
$env:FREETOKEN_HOME = Join-Path $Root ".freetoken"
$env:APPDATA = Join-Path $Root ".cache\windows\AppData"
$env:LOCALAPPDATA = Join-Path $Root ".cache\windows\LocalAppData"
$env:TEMP = Join-Path $Root ".tmp"
$env:TMP = Join-Path $Root ".tmp"

$UvZip = Join-Path $Root "tools\downloads\uv-x86_64-pc-windows-msvc.zip"
Download-Verified $Config.uv.url $UvZip $Config.uv.sha256
$UvExtract = Join-Path $Root "tools\uv"
Get-ChildItem -Force $UvExtract -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
Expand-Archive -Force -Path $UvZip -DestinationPath $UvExtract
$UvExe = (Get-ChildItem -Recurse -Path $UvExtract -Filter "uv.exe" | Select-Object -First 1).FullName
if (-not $UvExe) { throw "uv.exe was not found in the verified uv archive." }

Write-Host "[Setup] Provisioning project-local Python $($Config.python_version)"
& $UvExe python install $Config.python_version
if ($LASTEXITCODE -ne 0) { throw "uv python install failed." }
$HarnessVenv = Join-Path $Root ".venv"
& $UvExe venv $HarnessVenv --python $Config.python_version --managed-python --clear
if ($LASTEXITCODE -ne 0) { throw "Harness venv creation failed." }
& $UvExe pip install --python (Join-Path $HarnessVenv "Scripts\python.exe") -r (Join-Path $Root "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Harness dependency install failed." }

# Keep the original wheel filenames: Python package installers validate wheel tags from the filename.
$RuntimeWheel = Join-Path $Root "tools\downloads\freetoken-0.1.2+g141c31a8d-cp312-cp312-win_amd64.whl"
$KernelWheel = Join-Path $Root "tools\downloads\freetoken_kernel_cache-0.1.2+cu130.g141c31a8d-py3-none-win_amd64.whl"
Download-Verified $Config.freetoken.wheel_url $RuntimeWheel $Config.freetoken.wheel_sha256
Download-Verified $Config.freetoken.kernel_cache_url $KernelWheel $Config.freetoken.kernel_cache_sha256

$FtVenv = Join-Path $Root ".venvs\freetoken"
& $UvExe venv $FtVenv --python $Config.python_version --managed-python --clear
if ($LASTEXITCODE -ne 0) { throw "FreeToken venv creation failed." }
$FtPython = Join-Path $FtVenv "Scripts\python.exe"
Write-Host "[Setup] Installing official Windows FreeToken engine into .venvs\freetoken"
& $UvExe pip install --python $FtPython `
    "--torch-backend=$($Config.torch_backend)" `
    --reinstall-package freetoken `
    --reinstall-package freetoken-kernel-cache `
    --refresh-package freetoken `
    --refresh-package freetoken-kernel-cache `
    $RuntimeWheel $KernelWheel
if ($LASTEXITCODE -ne 0) { throw "FreeToken engine install failed." }

$FtExe = Join-Path $FtVenv "Scripts\ft.exe"
if (-not (Test-Path $FtExe)) { throw "Project-local ft.exe is missing after install." }
& $FtExe --help | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Project-local ft.exe self-check failed." }

$Provenance = [ordered]@{ schema_version = 1; installed_at = [DateTimeOffset]::UtcNow.ToString("o"); tool_root = $Root; uv_version = $Config.uv.version; uv_sha256 = $Config.uv.sha256; python_version = $Config.python_version; freetoken_version = $Config.freetoken.version; freetoken_wheel_sha256 = $Config.freetoken.wheel_sha256; kernel_cache_sha256 = $Config.freetoken.kernel_cache_sha256; venv = $FtVenv; self_contained = $true; python_registry_disabled = $true }
$Provenance | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 (Join-Path $Root "state\windows-setup.json")
Write-Host ""
Write-Host "[Setup] READY"
Write-Host "  Harness Python: $HarnessVenv"
Write-Host "  FreeToken:      $FtVenv"
Write-Host "  Models:         $(Join-Path $Root 'models')"
Write-Host "  Caches:         $(Join-Path $Root '.cache')"
Write-Host "  No FreeToken Desktop/AppData/global-Python registration was used."
