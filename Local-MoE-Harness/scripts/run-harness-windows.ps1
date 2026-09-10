$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Project-local harness environment is missing. Run Setup.bat." }

$Existing = Get-NetTCPConnection -LocalPort 1919 -State Listen -ErrorAction SilentlyContinue
if ($Existing) {
    $Managed = $false
    $PidPath = Join-Path $Root "state\freetoken.pid"
    if (Test-Path $PidPath) {
        $ManagedPid = (Get-Content -Raw $PidPath).Trim()
        foreach ($Item in $Existing) { if ("$($Item.OwningProcess)" -eq $ManagedPid) { $Managed = $true } }
    }
    if (-not $Managed) { throw "Port 1919 is already owned by an external process. Self-contained mode refuses to adopt it." }
}

$env:PYTHONPATH = $Root
$env:HF_HOME = Join-Path $Root "models\hf_cache"
$env:HUGGINGFACE_HUB_CACHE = Join-Path $Root "models\hf_cache\hub"
$env:XDG_CACHE_HOME = Join-Path $Root ".cache"
$env:PIP_CACHE_DIR = Join-Path $Root ".cache\pip"
$env:APPDATA = Join-Path $Root ".cache\windows\AppData"
$env:LOCALAPPDATA = Join-Path $Root ".cache\windows\LocalAppData"
$env:TEMP = Join-Path $Root ".tmp"
$env:TMP = Join-Path $Root ".tmp"
New-Item -ItemType Directory -Force -Path $env:APPDATA,$env:LOCALAPPDATA,$env:TEMP | Out-Null

& $Python -m uvicorn app.main:app --host 127.0.0.1 --port 5180
exit $LASTEXITCODE
