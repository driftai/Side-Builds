@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

set "ROOT=%CD%"
set "RUNTIME=%ROOT%\.runtime"

echo.
echo Stopping WatchParty LAN...
echo.

if exist "%RUNTIME%\remote-url.txt" (
    echo Remote WatchParty is currently active.
    echo Stop Remote first before stopping the shared origin.
    echo.
    pause
    endlocal
    exit /b 1
)

powershell.exe -NoProfile -Command ^
    "$tcp = Get-NetTCPConnection -LocalPort 9085 -State Listen -ErrorAction SilentlyContinue;" ^
    "if ($tcp) {" ^
    "    $ids = $tcp | Select-Object -ExpandProperty OwningProcess -Unique;" ^
    "    foreach ($id in $ids) {" ^
    "        $p = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $id) -ErrorAction SilentlyContinue;" ^
    "        if ($p -and $p.Name -eq 'node.exe' -and [string]$p.CommandLine -match 'server\.js') {" ^
    "            Write-Host ('Stopping WatchParty LAN Node PID ' + $id + '...');" ^
    "            Stop-Process -Id $id -Force -ErrorAction SilentlyContinue;" ^
    "        }" ^
    "    }" ^
    "}"

timeout /t 1 /nobreak >nul

del /q "%RUNTIME%\lan.active" >nul 2>&1
del /q "%RUNTIME%\local.active" >nul 2>&1
del /q "%RUNTIME%\lan-server.pid" >nul 2>&1

call "%ROOT%\scripts\SYNC-WATCHPARTY-STATE.bat"

echo.
echo ============================================================
echo LAN WatchParty stopped.
echo ============================================================
echo.

pause
endlocal
exit /b 0
