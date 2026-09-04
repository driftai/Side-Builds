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
Write-Host "Managed server PID: $ServerPid"
Write-Host "Port:               $Port"
Write-Host "Output log:         $StdoutLog"
Write-Host "Error log:          $StderrLog"
Write-Host ''
Write-Host 'This window is a live view of the managed background router.' -ForegroundColor DarkGray
Write-Host 'Use control.bat to stop/panic/toggle Cloudflare; closing this viewer' -ForegroundColor DarkGray
Write-Host 'does not stop the router.' -ForegroundColor DarkGray
Write-Host '======================================================================' -ForegroundColor Cyan
Write-Host ''

$seenOut = 0
$seenErr = 0

function Show-NewLines([string]$Path, [string]$Prefix, [ConsoleColor]$Color) {
    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }
    $lines = @(Get-Content -LiteralPath $Path -ErrorAction SilentlyContinue)
    $seen = if ($Prefix -eq '[ERR] ') { $script:seenErr } else { $script:seenOut }
    if ($lines.Count -gt $seen) {
        for ($index = $seen; $index -lt $lines.Count; $index++) {
            Write-Host ($Prefix + $lines[$index]) -ForegroundColor $Color
        }
    }
    if ($Prefix -eq '[ERR] ') {
        $script:seenErr = $lines.Count
    } else {
        $script:seenOut = $lines.Count
    }
}

while (Get-Process -Id $ServerPid -ErrorAction SilentlyContinue) {
    Show-NewLines $StdoutLog '' Gray
    Show-NewLines $StderrLog '[ERR] ' Yellow
    Start-Sleep -Milliseconds 250
}

Show-NewLines $StdoutLog '' Gray
Show-NewLines $StderrLog '[ERR] ' Yellow
Write-Host ''
Write-Host '======================================================================' -ForegroundColor Cyan
Write-Host 'Router process stopped. This runtime viewer can now be closed.' -ForegroundColor Yellow
Write-Host '======================================================================' -ForegroundColor Cyan
Read-Host 'Press Enter to close' | Out-Null
