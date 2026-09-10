param(
    [Parameter(Mandatory=$true)][string]$ModelPath,
    [int]$Port = 1919
)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$FtPython = Join-Path $Root ".venvs\freetoken\Scripts\python.exe"
$EntryPoint = Join-Path $Root "scripts\windows-freetoken-entry.py"
if (-not (Test-Path $FtPython)) { throw "Project-local FreeToken is missing at $FtPython. Run Setup.bat." }
if (-not (Test-Path $EntryPoint)) { throw "Windows FreeToken entry wrapper is missing at $EntryPoint." }

$Dirs = @(".cache", ".cache\windows\AppData", ".cache\windows\LocalAppData", ".tmp", "models\hf_cache", "logs", "state")
foreach ($Relative in $Dirs) { New-Item -ItemType Directory -Force -Path (Join-Path $Root $Relative) | Out-Null }

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
$env:LOCAL_MOE_PROJECT_ROOT = $Root

$MemoryRatio = if ($env:LOCAL_MOE_MEMORY_RATIO) { $env:LOCAL_MOE_MEMORY_RATIO } else { "0.90" }
$KvTokens = if ($env:LOCAL_MOE_KV_RESERVE_TOKENS) { $env:LOCAL_MOE_KV_RESERVE_TOKENS } else { "4096" }
$Prefill = if ($env:LOCAL_MOE_MAX_PREFILL_LENGTH) { $env:LOCAL_MOE_MAX_PREFILL_LENGTH } else { "1024" }
$MaxRequests = if ($env:LOCAL_MOE_MAX_RUNNING_REQUESTS) { $env:LOCAL_MOE_MAX_RUNNING_REQUESTS } else { "1" }
$Graph = if ($env:LOCAL_MOE_CUDA_GRAPH_MAX_BS) { $env:LOCAL_MOE_CUDA_GRAPH_MAX_BS } else { "0" }
$ServedName = if ($env:LOCAL_MOE_SERVED_MODEL_NAME) { $env:LOCAL_MOE_SERVED_MODEL_NAME } else { $ModelPath }

$Args = @("serve", "--model-path", $ModelPath, "--served-model-name", $ServedName, "--port", "$Port", "--host", "127.0.0.1", "--memory-ratio", "$MemoryRatio", "--kv-reserve-tokens", "$KvTokens", "--max-prefill-length", "$Prefill", "--max-running-requests", "$MaxRequests", "--cuda-graph-max-bs", "$Graph", "--cache-type", "radix", "--enable-cache-report", "--sampling-defaults", "model", "--disable-moe-prefill-overlap")
if ($env:LOCAL_MOE_PREFILL_HIT_D2D -eq "1") { $Args += "--moe-prefill-hit-d2d" }
if ($env:LOCAL_MOE_MOE_CACHE_SIZE) { $Args += @("--moe-cache-size", $env:LOCAL_MOE_MOE_CACHE_SIZE) }

Write-Host "[FreeToken/Windows] Project root: $Root"
Write-Host "[FreeToken/Windows] Engine: $FtPython $EntryPoint"
Write-Host "[FreeToken/Windows] Model: $ModelPath"
Write-Host "[FreeToken/Windows] Cache root: $(Join-Path $Root '.cache')"
Write-Host "[FreeToken/Windows] GGUF policy: release-qualified prebuilt only; no compiler/JIT fallback"
& $FtPython $EntryPoint @Args
exit $LASTEXITCODE
