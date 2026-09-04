param(
    [Parameter(Mandatory = $true)]
    [int]$ServerPid,
    [Parameter(Mandatory = $true)]
    [int]$Port,
    [Parameter(Mandatory = $true)]
    [string]$StdoutLog,
    [Parameter(Mandatory = $true)]
    [string]$StderrLog
)

$ErrorActionPreference = 'SilentlyContinue'
$Host.UI.RawUI.WindowTitle = "OmniPad Router Runtime - Port $Port"

Write-Host '======================================================================' -ForegroundColor Cyan
Write-Host '                  OMNIPAD ROUTER RUNTIME' -ForegroundColor Cyan
Write-Host '======================================================================' -ForegroundColor Cyan
Write-Host "Managed launcher PID: $ServerPid"
Write-Host "Port:                 $Port"
Write-Host "Output log:           $StdoutLog"
Write-Host "Runtime log:          $StderrLog"
Write-Host ''
Write-Host 'This is a live view of the managed background router.' -ForegroundColor DarkGray
Write-Host 'Use control.bat to stop/panic/toggle Cloudflare. Closing only this' -ForegroundColor DarkGray
Write-Host 'viewer does not stop the router; option V reopens it.' -ForegroundColor DarkGray
Write-Host '======================================================================' -ForegroundColor Cyan
Write-Host ''

$outState = @{ Position = [int64]0; Carry = ''; IsRuntime = $false }
$runtimeState = @{ Position = [int64]0; Carry = ''; IsRuntime = $true }

function Write-RuntimeLine([string]$Line, [bool]$RuntimeStream) {
    if (-not $RuntimeStream) {
        Write-Host $Line -ForegroundColor Gray
        return
    }
    if ($Line -match '(^ERROR:|\[ERROR\]|Traceback|Exception|WinError)') {
        Write-Host ("[ERROR] " + $Line) -ForegroundColor Red
    } elseif ($Line -match '(^WARNING:|\[WARNING\])') {
        Write-Host ("[WARN] " + $Line) -ForegroundColor Yellow
    } else {
        # Uvicorn writes ordinary INFO lifecycle messages to stderr. Display
        # those as runtime information instead of falsely labelling them errors.
        Write-Host $Line -ForegroundColor DarkGray
    }
}

function Show-NewLogText([string]$Path, [hashtable]$State) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    $stream = $null
    try {
        $stream = [IO.File]::Open($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
        if ($stream.Length -lt $State.Position) {
            $State.Position = [int64]0
            $State.Carry = ''
        }
        $available = [int]($stream.Length - $State.Position)
        if ($available -le 0) { return }
        [void]$stream.Seek($State.Position, [IO.SeekOrigin]::Begin)
        $buffer = New-Object byte[] $available
        $read = $stream.Read($buffer, 0, $available)
        $State.Position += $read
        $text = $State.Carry + [Text.Encoding]::UTF8.GetString($buffer, 0, $read)
        $lines = @($text -split "`r?`n", -1)
        $State.Carry = $lines[-1]
        for ($index = 0; $index -lt ($lines.Count - 1); $index++) {
            Write-RuntimeLine $lines[$index] $State.IsRuntime
        }
    } finally {
        if ($stream) { $stream.Dispose() }
    }
}

while (Get-Process -Id $ServerPid -ErrorAction SilentlyContinue) {
    Show-NewLogText $StdoutLog $outState
    Show-NewLogText $StderrLog $runtimeState
    Start-Sleep -Milliseconds 250
}

Show-NewLogText $StdoutLog $outState
Show-NewLogText $StderrLog $runtimeState
Write-Host ''
Write-Host '======================================================================' -ForegroundColor Cyan
Write-Host 'Router process stopped. This runtime viewer can now be closed.' -ForegroundColor Yellow
Write-Host '======================================================================' -ForegroundColor Cyan
Write-Host 'Closing this viewer in 5 seconds...' -ForegroundColor DarkGray
Start-Sleep -Seconds 5
