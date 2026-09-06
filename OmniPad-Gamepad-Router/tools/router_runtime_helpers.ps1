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

function Start-RuntimeViewer([object]$State) {
    if ($State.viewer_pid -and (Get-ProcessRecord ([int]$State.viewer_pid))) {
        Write-Host "Runtime console is already open (PID $($State.viewer_pid))." -ForegroundColor Green
        return
    }
    if (-not (Test-Path -LiteralPath $runtimeViewer)) {
        throw "Runtime viewer is missing: $runtimeViewer"
    }
    $arguments = @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $runtimeViewer + '"'),
        '-ServerPid', [string]$State.pid,
        '-Port', [string]$State.port,
        '-StdoutLog', ('"' + $stdoutLog + '"'),
        '-StderrLog', ('"' + $stderrLog + '"')
    )
    $viewer = Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments `
        -WorkingDirectory $root -WindowStyle Normal -PassThru
    $State | Add-Member -NotePropertyName viewer_pid -NotePropertyValue $viewer.Id -Force
    Write-ControlState $State
    Write-Host "Runtime console opened (viewer PID $($viewer.Id))." -ForegroundColor Green
}
