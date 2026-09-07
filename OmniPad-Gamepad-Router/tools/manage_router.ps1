param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Start', 'Status', 'Stop', 'StartTunnel', 'StopTunnel', 'Panic', 'OpenDashboard', 'ShowRuntime', 'Cleanup')]
    [string]$Action,
    [ValidateSet('lan', 'tunnel')]
    [string]$Mode = 'lan',
    [ValidateRange(1, 65535)]
    [int]$Port = 8000,
    [switch]$Confirmed
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $root '.venv\Scripts\python.exe'
$serverPath = Join-Path $root 'server.py'
$runtimeDirectory = Join-Path $root '.runtime'
$statePath = Join-Path $runtimeDirectory 'omnipad-control.json'
$logDirectory = Join-Path $root 'logs'
$stdoutLog = Join-Path $logDirectory 'omnipad-control.out.log'
$stderrLog = Join-Path $logDirectory 'omnipad-control.err.log'
$runtimeViewer = Join-Path $PSScriptRoot 'watch_router_runtime.ps1'
. (Join-Path $PSScriptRoot 'router_runtime_helpers.ps1')

function Show-RouterStatus {
    $state = Read-ControlState
    if (-not $state) {
        $unmanaged = @(Get-RepoServerRecords)
        if ($unmanaged.Count -gt 0) {
            Write-Host "Router: RUNNING OUTSIDE CONTROL STATE (PID(s): $($unmanaged.ProcessId -join ', '))" -ForegroundColor Yellow
            Write-Host 'Use scoped cleanup to stop only these exact repository processes.'
            return
        }
        Write-Host 'Router: STOPPED (no managed session)' -ForegroundColor Yellow
        return
    }
    if (-not (Test-ManagedProcess $state)) {
        Write-Host "Router: STOPPED (stale state for PID $($state.pid))" -ForegroundColor Yellow
        Write-Host "State:  $statePath"
        return
    }
    $status = Get-RouterStatus $state
    Write-Host 'Router: RUNNING' -ForegroundColor Green
    Write-Host "PID:    $($state.pid)"
    Write-Host "Mode:   $($state.mode)"
    Write-Host "Port:   $($state.port)"
    Write-Host "Host:   http://localhost:$($state.port)/"
    if ($state.viewer_pid -and (Get-ProcessRecord ([int]$state.viewer_pid))) {
        Write-Host "Viewer: PID $($state.viewer_pid) (visible runtime console)"
    } else {
        Write-Host 'Viewer: closed (use control.bat option V to reopen)'
    }
    if ($status) {
        Write-Host "Room:   $($status.room_code)"
        if ($status.primary_lan_url) {
            Write-Host "LAN:    $($status.primary_lan_url)"
        }
        $tunnelStatus = [string]$status.tunnel.status
        Write-Host "Tunnel: $tunnelStatus"
        if ($status.tunnel.public_url) {
            Write-Host "Player: $($status.tunnel.public_url)/play?code=$($status.room_code)"
        }
        Write-Host "UMDF:   $($status.umdf_keyboard_available)"
    } else {
        Write-Host 'Health: process exists, API is not responding' -ForegroundColor Yellow
    }
    Write-Host "Logs:   $stdoutLog"
}

function Start-Router {
    if (-not (Test-Path -LiteralPath $python)) {
        throw "Python environment is missing: $python. Run tools\setup_env.bat first."
    }
    $existing = Read-ControlState
    if (Test-ManagedProcess $existing) {
        if ($Mode -eq 'tunnel') {
            $status = Get-RouterStatus $existing
            $tunnelStatus = if ($status) { [string]$status.tunnel.status } else { '' }
            if ($tunnelStatus -notin @('online', 'starting')) {
                $response = Invoke-ControlApi $existing 'POST' '/api/tunnel/start'
                if (-not $response.ok) { throw 'Existing LAN router is running, but its Cloudflare tunnel failed to start.' }
            }
            $existing.mode = 'tunnel'
            Write-ControlState $existing
            Write-Host 'Existing LAN router upgraded to Cloudflare + LAN mode.' -ForegroundColor Green
        }
        Start-RuntimeViewer $existing
        Show-RouterStatus
        if ($Mode -ne 'tunnel') {
            Write-Host 'The existing managed router was left running.' -ForegroundColor Yellow
        }
        return
    }
    if ($existing) {
        Remove-ControlState
    }
    $unmanaged = @(Get-RepoServerRecords)
    if ($unmanaged.Count -gt 0) {
        throw "An unmanaged server from this repository is already running (PID(s): $($unmanaged.ProcessId -join ', ')). Use scoped cleanup first."
    }

    New-Item -ItemType Directory -Path $runtimeDirectory -Force | Out-Null
    New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
    $quotedServer = '"' + $serverPath.Replace('"', '\"') + '"'
    $arguments = @('-u', $quotedServer, '--port', [string]$Port)
    if ($Mode -eq 'tunnel') {
        $arguments += '--tunnel'
    }
    $startParameters = @{
        FilePath = $python
        ArgumentList = $arguments
        WorkingDirectory = $root
        WindowStyle = 'Hidden'
        RedirectStandardOutput = $stdoutLog
        RedirectStandardError = $stderrLog
        PassThru = $true
    }
    $process = Start-Process @startParameters

    $state = [ordered]@{
        pid = $process.Id
        port = $Port
        mode = $Mode
        started_at = (Get-Date).ToUniversalTime().ToString('o')
        server_path = $serverPath
        stdout_log = $stdoutLog
        stderr_log = $stderrLog
    }
    Write-ControlState $state

    $ready = $false
    for ($attempt = 0; $attempt -lt 100; $attempt++) {
        if ($process.HasExited) {
            break
        }
        if (Get-RouterStatus $state) {
            $ready = $true
            break
        }
        Start-Sleep -Milliseconds 100
    }
    if (-not $ready) {
        if ($process.HasExited) {
            Remove-ControlState
        }
        $tail = if (Test-Path -LiteralPath $stderrLog) {
            (Get-Content -LiteralPath $stderrLog -Tail 12) -join [Environment]::NewLine
        } else { 'No error log was created.' }
        throw "Router did not become ready.`n$tail"
    }
    Start-RuntimeViewer $state
    Show-RouterStatus
}

function Wait-ForExit([int]$TargetProcessId, [int]$Milliseconds) {
    $deadline = [DateTime]::UtcNow.AddMilliseconds($Milliseconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if (-not (Get-ProcessRecord $TargetProcessId)) {
            return $true
        }
        Start-Sleep -Milliseconds 100
    }
    return -not [bool](Get-ProcessRecord $TargetProcessId)
}

function Stop-ManagedState([object]$State) {
    if (-not (Test-ManagedProcess $State)) {
        Remove-ControlState
        Write-Host 'Router is already stopped; stale control state was cleared.' -ForegroundColor Yellow
        return
    }

    $targetId = [int]$State.pid
    $descendants = @(Get-DescendantProcessIds $targetId)
    $graceful = $false
    try {
        $response = Invoke-ControlApi $State 'POST' '/api/control/shutdown'
        $graceful = [bool]$response.ok
    } catch {
        Write-Warning 'Graceful API shutdown was unavailable; using scoped process fallback.'
        try { Invoke-ControlApi $State 'POST' '/api/panic' | Out-Null } catch {}
        try { Invoke-ControlApi $State 'POST' '/api/tunnel/stop' | Out-Null } catch {}
        try {
            Invoke-ControlApi $State 'POST' '/api/background-capture' @{ enabled = $false; slot_id = 1 } | Out-Null
        } catch {}
    }

    if (-not (Wait-ForExit $targetId 10000)) {
        foreach ($childId in $descendants) {
            Stop-Process -Id $childId -Force -ErrorAction SilentlyContinue
        }
        Stop-Process -Id $targetId -Force -ErrorAction Stop
        Wait-ForExit $targetId 3000 | Out-Null
        $graceful = $false
    }
    Remove-ControlState
    if ($graceful) {
        Write-Host 'Router stopped gracefully; outputs, helper, and tunnel were released.' -ForegroundColor Green
    } else {
        Write-Host 'Router stopped through the exact managed process scope.' -ForegroundColor Yellow
        Write-Host 'The UMDF driver watchdog independently releases held keys within 750 ms.'
    }
}

function Require-RunningState {
    $state = Read-ControlState
    if (-not (Test-ManagedProcess $state)) {
        throw 'No managed OmniPad router is running.'
    }
    return $state
}

function Stop-UntrackedRepoServers {
    $records = @(Get-RepoServerRecords)
    if ($records.Count -eq 0) {
        Write-Host 'Router: STOPPED (no managed or repository server process)' -ForegroundColor Yellow
        return
    }
    foreach ($record in $records) {
        if (-not (Get-ProcessRecord ([int]$record.ProcessId))) {
            continue
        }
        $recordPort = 8000
        if ([string]$record.CommandLine -match '--port\s+(\d+)') {
            $recordPort = [int]$Matches[1]
        }
        $temporaryState = [pscustomobject]@{
            pid = [int]$record.ProcessId
            port = $recordPort
            mode = 'untracked'
        }
        Stop-ManagedState $temporaryState
    }
}

function Cleanup-RepoProcesses {
    if (-not $Confirmed) {
        throw 'Cleanup requires -Confirmed after showing the exact repository scope.'
    }
    $state = Read-ControlState
    if (Test-ManagedProcess $state) {
        Stop-ManagedState $state
    }
    if (@(Get-RepoServerRecords).Count -gt 0) {
        Stop-UntrackedRepoServers
    }
    Remove-ControlState
    Write-Host "Scoped cleanup complete for: $serverPath" -ForegroundColor Green
}

try {
    switch ($Action) {
    'Start' { Start-Router }
    'Status' { Show-RouterStatus }
    'Stop' {
        $state = Read-ControlState
        if ($state -and (Test-ManagedProcess $state)) {
            Stop-ManagedState $state
        } else {
            Remove-ControlState
            Stop-UntrackedRepoServers
        }
    }
    'StartTunnel' {
        $state = Require-RunningState
        Start-RuntimeViewer $state
        $response = Invoke-ControlApi $state 'POST' '/api/tunnel/start'
        if (-not $response.ok) { throw 'Tunnel failed to start.' }
        $state.mode = 'tunnel'
        Write-ControlState $state
        Write-Host 'Cloudflare tunnel start requested.' -ForegroundColor Green
        Show-RouterStatus
    }
    'StopTunnel' {
        $state = Read-ControlState
        if (-not (Test-ManagedProcess $state)) {
            Write-Host 'Cloudflare tunnel is already stopped; no managed router is running.' -ForegroundColor Yellow
            break
        }
        Invoke-ControlApi $state 'POST' '/api/tunnel/stop' | Out-Null
        $state.mode = 'lan'
        Write-ControlState $state
        Write-Host 'Cloudflare tunnel stopped; LAN router remains online.' -ForegroundColor Green
    }
    'Panic' {
        $state = Read-ControlState
        if (-not (Test-ManagedProcess $state)) {
            Write-Host 'No managed router is running; there are no routed inputs to release.' -ForegroundColor Yellow
            break
        }
        Invoke-ControlApi $state 'POST' '/api/panic' | Out-Null
        Write-Host 'All virtual controller and keyboard outputs released.' -ForegroundColor Green
    }
    'OpenDashboard' {
        $state = Require-RunningState
        Start-Process "http://localhost:$($state.port)/"
    }
    'ShowRuntime' {
        $state = Require-RunningState
        Start-RuntimeViewer $state
    }
    'Cleanup' { Cleanup-RepoProcesses }
    }
} catch {
    Write-Host ("OmniPad control error: " + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
