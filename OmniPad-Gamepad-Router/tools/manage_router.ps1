param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Start', 'Status', 'Stop', 'StartTunnel', 'StopTunnel', 'Panic', 'OpenDashboard', 'Cleanup')]
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

function Read-ControlState {
    if (-not (Test-Path -LiteralPath $statePath)) {
        return $null
    }
    try {
        return Get-Content -Raw -LiteralPath $statePath | ConvertFrom-Json
    } catch {
        Write-Warning "Ignoring unreadable control state: $statePath"
        return $null
    }
}

function Write-ControlState([object]$State) {
    New-Item -ItemType Directory -Path $runtimeDirectory -Force | Out-Null
    $State | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $statePath -Encoding UTF8
}

function Remove-ControlState {
    if (Test-Path -LiteralPath $statePath) {
        Remove-Item -LiteralPath $statePath -Force
    }
}

function Get-ProcessRecord([int]$TargetProcessId) {
    return Get-CimInstance Win32_Process -Filter "ProcessId = $TargetProcessId" -ErrorAction SilentlyContinue
}

function Test-ServerCommandLine([string]$CommandLine) {
    return $CommandLine -and $CommandLine.IndexOf(
        $serverPath,
        [StringComparison]::OrdinalIgnoreCase
    ) -ge 0
}

function Get-RepoServerRecords {
    return @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -match '^python(w)?\.exe$' -and (Test-ServerCommandLine ([string]$_.CommandLine))
    })
}

function Test-ManagedProcess([object]$State) {
    if (-not $State -or -not $State.pid) {
        return $false
    }
    $record = Get-ProcessRecord ([int]$State.pid)
    if (-not $record) {
        return $false
    }
    return $record.Name -match '^python(w)?\.exe$' -and
        (Test-ServerCommandLine ([string]$record.CommandLine))
}

function Get-DescendantProcessIds([int]$ParentId) {
    $all = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
    $pending = [Collections.Generic.Queue[int]]::new()
    $result = [Collections.Generic.List[int]]::new()
    $pending.Enqueue($ParentId)
    while ($pending.Count -gt 0) {
        $current = $pending.Dequeue()
        foreach ($child in $all | Where-Object { [int]$_.ParentProcessId -eq $current }) {
            $childId = [int]$child.ProcessId
            $result.Add($childId)
            $pending.Enqueue($childId)
        }
    }
    return @($result)
}

function Invoke-ControlApi(
    [object]$State,
    [string]$Method,
    [string]$Path,
    [object]$Body = $null,
    [int]$TimeoutSec = 4
) {
    $uri = "http://127.0.0.1:$([int]$State.port)$Path"
    $parameters = @{
        Uri = $uri
        Method = $Method
        TimeoutSec = $TimeoutSec
        ErrorAction = 'Stop'
    }
    if ($null -ne $Body) {
        $parameters.ContentType = 'application/json'
        $parameters.Body = ($Body | ConvertTo-Json -Compress)
    }
    return Invoke-RestMethod @parameters
}

function Get-RouterStatus([object]$State) {
    try {
        return Invoke-ControlApi $State 'GET' '/api/status' $null 2
    } catch {
        return $null
    }
}

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
        Show-RouterStatus
        throw 'A managed OmniPad router is already running. Stop it before starting another.'
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
        $response = Invoke-ControlApi $state 'POST' '/api/tunnel/start'
        if (-not $response.ok) { throw 'Tunnel failed to start.' }
        $state.mode = 'tunnel'
        Write-ControlState $state
        Write-Host 'Cloudflare tunnel start requested.' -ForegroundColor Green
        Show-RouterStatus
    }
    'StopTunnel' {
        $state = Require-RunningState
        Invoke-ControlApi $state 'POST' '/api/tunnel/stop' | Out-Null
        $state.mode = 'lan'
        Write-ControlState $state
        Write-Host 'Cloudflare tunnel stopped; LAN router remains online.' -ForegroundColor Green
    }
    'Panic' {
        $state = Require-RunningState
        Invoke-ControlApi $state 'POST' '/api/panic' | Out-Null
        Write-Host 'All virtual controller and keyboard outputs released.' -ForegroundColor Green
    }
    'OpenDashboard' {
        $state = Require-RunningState
        Start-Process "http://localhost:$($state.port)/"
    }
    'Cleanup' { Cleanup-RepoProcesses }
    }
} catch {
    Write-Error $_.Exception.Message
    exit 1
}
