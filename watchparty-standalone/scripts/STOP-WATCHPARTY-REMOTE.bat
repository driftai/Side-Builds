@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

set "ROOT=%CD%"
set "RUNTIME=%ROOT%\.runtime"
set "PIDFILE=%RUNTIME%\cloudflared.pid"
set "CLOUDFLARED=%ROOT%\tools\cloudflared.exe"

echo.
echo Stopping WatchParty remote session...
echo.

set "FOUND=0"

REM ============================================================
REM 1. Try the tracked remote monitor / tunnel PID first
REM ============================================================

if exist "%PIDFILE%" (
    set /p TRACKEDPID=<"%PIDFILE%"

    if defined TRACKEDPID (
        echo Tracked remote PID: %TRACKEDPID%
        taskkill /PID %TRACKEDPID% /T /F >nul 2>&1

        if not errorlevel 1 (
            echo Tracked remote process tree stopped.
            set "FOUND=1"
        )
    )
)

REM ============================================================
REM 2. Find the actual bundled cloudflared.exe if needed
REM ============================================================

powershell.exe -NoProfile -Command ^
    "$target = [System.IO.Path]::GetFullPath('%CLOUDFLARED%');" ^
    "$procs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.ExecutablePath -and ([System.IO.Path]::GetFullPath($_.ExecutablePath) -ieq $target) };" ^
    "foreach ($p in $procs) { Write-Host ('Stopping cloudflared PID ' + $p.ProcessId + '...'); Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue; }"

REM ============================================================
REM 3. Kill generated Cloudflare runner / monitor wrappers
REM ============================================================

powershell.exe -NoProfile -Command ^
    "$runtime = '%RUNTIME%';" ^
    "$procs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue;" ^
    "foreach ($p in $procs) {" ^
    "  $cmd = [string]$p.CommandLine;" ^
    "  if ($cmd -and ($cmd -like ('*' + $runtime + '*RUN-CLOUDFLARE*'))) {" ^
    "    Write-Host ('Stopping Cloudflare runner PID ' + $p.ProcessId + '...');" ^
    "    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue;" ^
    "  }" ^
    "}"

REM ============================================================
REM 4. Remove session state
REM ============================================================

if exist "%RUNTIME%" (
    echo Cleaning remote session state...
    rmdir /s /q "%RUNTIME%" >nul 2>&1
)

echo.
echo ============================================================
echo Remote WatchParty session stopped.
echo ============================================================
echo.
echo The previous public Quick Tunnel URL is no longer active.
echo.
pause

endlocal
exit /b 0
