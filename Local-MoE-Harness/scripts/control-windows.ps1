param([ValidateSet("menu","start","status","stop","open","logs")][string]$Action = "menu")
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$State = Join-Path $Root "state"
$Logs = Join-Path $Root "logs"
$HarnessPidPath = Join-Path $State "harness.pid"
$RuntimePidPath = Join-Path $State "freetoken.pid"
$HarnessScript = Join-Path $Root "scripts\run-harness-windows.ps1"
$HarnessUrl = "http://127.0.0.1:5180"
New-Item -ItemType Directory -Force -Path $State,$Logs | Out-Null

function Repair-ProjectLocalVenvs {
    $Relocated = $false
    $PythonRoot = Join-Path $Root "tools\python"
    $RuntimeConfigPath = Join-Path $Root "config\windows-runtime.json"
    if (-not (Test-Path -LiteralPath $RuntimeConfigPath)) { return }
    $RuntimeConfig = Get-Content -LiteralPath $RuntimeConfigPath -Raw | ConvertFrom-Json
    $PythonAlias = Join-Path $PythonRoot "cpython-$($RuntimeConfig.python_version)-windows-x86_64-none"
    $ManagedPythons = @(
        Get-ChildItem -LiteralPath $PythonRoot -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -ne $PythonAlias -and (Test-Path (Join-Path $_.FullName "python.exe")) }
    )
    if ($ManagedPythons.Count -ne 1) { return }
    $ManagedPython = $ManagedPythons[0].FullName
    $AliasItem = Get-Item -LiteralPath $PythonAlias -Force -ErrorAction SilentlyContinue
    if ($AliasItem -and $AliasItem.LinkType -ne "Junction") {
        throw "Refusing to replace non-junction managed-Python alias: $PythonAlias"
    }
    if (-not (Test-Path -LiteralPath (Join-Path $PythonAlias "python.exe"))) {
        if ($AliasItem) { Remove-Item -LiteralPath $PythonAlias -Force }
        New-Item -ItemType Junction -Path $PythonAlias -Target $ManagedPython | Out-Null
        $Relocated = $true
        Write-Host "[Control] Repaired relocated managed-Python junction: $PythonAlias"
    }
    $PythonHome = $PythonAlias
    foreach ($ConfigPath in @(
        (Join-Path $Root ".venv\pyvenv.cfg"),
        (Join-Path $Root ".venvs\freetoken\pyvenv.cfg")
    )) {
        if (-not (Test-Path -LiteralPath $ConfigPath)) { continue }
        $Lines = @(Get-Content -LiteralPath $ConfigPath)
        $Found = $false
        $Updated = foreach ($Line in $Lines) {
            if ($Line -match '^home\s*=') { $Found = $true; "home = $PythonHome" } else { $Line }
        }
        if (-not $Found) { throw "Invalid project venv config: $ConfigPath" }
        if (($Lines -join "`n") -ne ($Updated -join "`n")) {
            Set-Content -LiteralPath $ConfigPath -Encoding UTF8 -Value $Updated
            $Relocated = $true
            Write-Host "[Control] Repaired relocated project environment: $ConfigPath"
        }
    }
    if ($Relocated) {
        $UvExe = Join-Path $Root "tools\uv\uv.exe"
        if (-not (Test-Path -LiteralPath $UvExe)) { throw "Project-local uv is missing: $UvExe" }
        $env:UV_CACHE_DIR = Join-Path $Root ".cache\uv"
        $env:UV_PYTHON_INSTALL_DIR = $PythonRoot
        $env:UV_PYTHON_NO_REGISTRY = "1"
        foreach ($VenvPath in @((Join-Path $Root ".venv"), (Join-Path $Root ".venvs\freetoken"))) {
            & $UvExe venv $VenvPath --python (Join-Path $PythonAlias "python.exe") --managed-python --allow-existing --no-progress | Out-Null
            if ($LASTEXITCODE -ne 0) { throw "Failed to repair relocated environment: $VenvPath" }
        }
    }
    $ProvenancePath = Join-Path $State "windows-setup.json"
    if (Test-Path -LiteralPath $ProvenancePath) {
        $Provenance = Get-Content -LiteralPath $ProvenancePath -Raw | ConvertFrom-Json
        if ($Provenance.tool_root -ne $Root) {
            $Provenance.tool_root = $Root
            $Provenance.venv = Join-Path $Root ".venvs\freetoken"
            $Provenance | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $ProvenancePath -Encoding UTF8
        }
    }
}

Repair-ProjectLocalVenvs

function Read-ManagedId([string]$Path) {
    if (-not (Test-Path $Path)) { return $null }
    $Raw = (Get-Content -Raw $Path).Trim()
    $Value = 0
    if ([int]::TryParse($Raw, [ref]$Value) -and $Value -gt 1) { return $Value }
    return $null
}
function Get-OwnedProcess([int]$ProcessId, [string[]]$ExpectedMarkers) {
    $Process = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
    if (-not $Process) { return $null }
    $Command = [string]$Process.CommandLine
    if (-not $Command) { return $null }
    $CmdLower = $Command.ToLowerInvariant()
    $RootLower = $Root.ToLowerInvariant()

    # PID files are only a hint: Windows can reuse a PID after the original process
    # exits. Fail closed unless the live process command line is rooted in this exact
    # Harness checkout. A matching script/module basename alone is never ownership.
    $HasRootPath = (
        $CmdLower.Contains($RootLower + "\") -or
        $CmdLower.Contains($RootLower + "/") -or
        $CmdLower.Contains('"' + $RootLower + '"') -or
        $CmdLower.EndsWith($RootLower)
    )
    if (-not $HasRootPath) { return $null }

    foreach ($Marker in $ExpectedMarkers) {
        $MLower = $Marker.ToLowerInvariant()
        if ($CmdLower.Contains($MLower)) { return $Process }
    }
    return $null
}
function Stop-OwnedTree([string]$IdPath, [string]$Name, [string[]]$Markers) {
    $ProcessId = Read-ManagedId $IdPath
    if (-not $ProcessId) { Remove-Item -Force $IdPath -ErrorAction SilentlyContinue; Write-Host "[Control] $Name is not running under this tool."; return }
    $LiveProcess = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if (-not $LiveProcess) {
        Remove-Item -Force $IdPath -ErrorAction SilentlyContinue
        Write-Host "[Control] $Name (PID $ProcessId) is already stopped."
        return
    }
    $Owned = Get-OwnedProcess $ProcessId $Markers
    if (-not $Owned) { Write-Warning "Refusing to stop PID $ProcessId because it is not verified as this tool's $Name."; Remove-Item -Force $IdPath -ErrorAction SilentlyContinue; return }
    Write-Host "[Control] Stopping $Name process tree (PID $ProcessId)..."
    & taskkill.exe /PID $ProcessId /T /F | Out-Null
    Remove-Item -Force $IdPath -ErrorAction SilentlyContinue
}
function Test-Harness {
    try {
        # Live status includes host telemetry and may take several seconds.
        # The OpenAPI title is a lightweight, app-specific readiness check.
        $Document = Invoke-RestMethod -Uri "$HarnessUrl/openapi.json" -TimeoutSec 5
        return $Document.info.title -eq "Local MoE Harness"
    } catch { return $false }
}
function Start-Harness {
    if (Test-Harness) { Write-Host "[Control] Harness is already online."; Start-Process $HarnessUrl; return }
    if (-not (Test-Path (Join-Path $Root ".venv\Scripts\python.exe"))) { throw "Setup is incomplete. Run Setup.bat first." }
    $ExistingId = Read-ManagedId $HarnessPidPath
    if ($ExistingId -and (Get-OwnedProcess $ExistingId @("run-harness-windows.ps1"))) { Write-Host "[Control] Harness process $ExistingId is already starting." }
    else {
        Remove-Item -Force $HarnessPidPath -ErrorAction SilentlyContinue
        $OutLog = Join-Path $Logs "harness-server.log"
        $ErrLog = Join-Path $Logs "harness-server-error.log"
        $Args = @("-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", "`"$HarnessScript`"")
        $Process = Start-Process powershell.exe -ArgumentList $Args -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog -PassThru
        Set-Content -Encoding ASCII -Path $HarnessPidPath -Value $Process.Id
        Write-Host "[Control] Harness launcher PID: $($Process.Id)"
    }
    Write-Host "[Control] Waiting for localhost:5180..."
    $Deadline = (Get-Date).AddMinutes(8)
    while ((Get-Date) -lt $Deadline) {
        if (Test-Harness) { Write-Host "[Control] Harness is online."; Start-Process $HarnessUrl; return }
        $ManagedId = Read-ManagedId $HarnessPidPath
        if (-not $ManagedId -or -not (Get-Process -Id $ManagedId -ErrorAction SilentlyContinue)) {
            Write-Host "[Control] Harness exited before becoming ready."
            if (Test-Path (Join-Path $Logs "harness-server-error.log")) { Get-Content -Tail 40 (Join-Path $Logs "harness-server-error.log") }
            throw "Harness startup failed."
        }
        Start-Sleep -Milliseconds 750
    }
    throw "Harness did not become reachable within the startup budget."
}
function Show-Status {
    $HarnessId = Read-ManagedId $HarnessPidPath
    $RuntimeId = Read-ManagedId $RuntimePidPath
    Write-Host "=== Local MoE Harness Status ==="
    Write-Host "Root:      $Root"
    Write-Host "Harness:   $(if ($HarnessId) { "PID $HarnessId" } else { "not managed" })"
    Write-Host "FreeToken: $(if ($RuntimeId) { "PID $RuntimeId" } else { "not managed" })"
    try { $Status = Invoke-RestMethod -Uri "$HarnessUrl/api/status" -TimeoutSec 15; Write-Host "HTTP:      online"; Write-Host "Runtime:   $($Status.runtime.health_status)"; if ($Status.runtime.models -and $Status.runtime.models.Count -gt 0) { Write-Host "Model:     $($Status.runtime.models[0].id)" } } catch { Write-Host "HTTP:      offline" }
}
function Stop-All { Stop-OwnedTree $RuntimePidPath "FreeToken" @("run-freetoken-windows.ps1", ".venvs\freetoken\scripts\python.exe", "windows-freetoken-entry.py", "freetoken"); Stop-OwnedTree $HarnessPidPath "harness" @("run-harness-windows.ps1", ".venv", "uvicorn", "app.main") }
function Invoke-Action([string]$Name) { switch ($Name) { "start" { Start-Harness }; "status" { Show-Status }; "stop" { Stop-All }; "open" { Start-Process $HarnessUrl }; "logs" { Start-Process explorer.exe $Logs }; default { throw "Unknown action: $Name" } } }
if ($Action -ne "menu") { Invoke-Action $Action; exit 0 }
while ($true) {
    Clear-Host
    Write-Host "====================================================="; Write-Host "               LOCAL MOE HARNESS"; Write-Host "====================================================="; Write-Host ""
    Write-Host " [1] Start + Open Chat"; Write-Host " [2] Show Status"; Write-Host " [3] Open Chat"; Write-Host " [4] Stop Everything"; Write-Host " [5] Open Logs"; Write-Host " [6] Exit"; Write-Host ""
    $Choice = Read-Host "Select an option"
    try { switch ($Choice) { "1" { Start-Harness }; "2" { Show-Status }; "3" { Start-Process $HarnessUrl }; "4" { Stop-All }; "5" { Start-Process explorer.exe $Logs }; "6" { break }; default { Write-Host "Invalid option." } } } catch { Write-Host ""; Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red }
    if ($Choice -eq "6") { break }
    Write-Host ""; Read-Host "Press Enter to continue" | Out-Null
}
