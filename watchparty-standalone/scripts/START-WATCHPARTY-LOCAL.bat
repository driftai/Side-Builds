@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

set "ROOT=%CD%"
set "RUNTIME=%ROOT%\.runtime"
title WatchParty Standalone - Local

if not exist "%ROOT%\server.js" (
    echo ERROR: server.js was not found in:
    echo %ROOT%
    pause
    exit /b 1
)

if exist "%RUNTIME%\remote-url.txt" (
    echo.
    echo WatchParty Remote is currently active.
    echo Stop Remote before starting Local mode.
    echo.
    pause
    exit /b 1
)

if exist "%RUNTIME%\lan.active" (
    echo.
    echo WatchParty LAN is currently active.
    echo Stop LAN before starting Local mode.
    echo.
    pause
    exit /b 1
)

REM Fresh runtime state because no other WatchParty mode is active.
if exist "%RUNTIME%" (
    rmdir /s /q "%RUNTIME%" >nul 2>&1
)

mkdir "%RUNTIME%" >nul 2>&1

REM Automatically clean a stale WatchParty server on 9085.
powershell.exe -NoProfile -Command ^
    "$tcp=Get-NetTCPConnection -LocalPort 9085 -State Listen -ErrorAction SilentlyContinue;" ^
    "if($tcp) {" ^
    "  $ids=$tcp | Select-Object -ExpandProperty OwningProcess -Unique;" ^
    "  foreach($id in $ids) {" ^
    "    $p=Get-CimInstance Win32_Process -Filter ('ProcessId=' + $id) -ErrorAction SilentlyContinue;" ^
    "    if($p -and $p.Name -eq 'node.exe' -and [string]$p.CommandLine -match 'server\.js') {" ^
    "      Write-Host ('Cleaning stale WatchParty server PID ' + $id + '...');" ^
    "      Stop-Process -Id $id -Force -ErrorAction SilentlyContinue;" ^
    "    }" ^
    "  }" ^
    "}"

timeout /t 1 /nobreak >nul

powershell.exe -NoProfile -Command ^
    "$tcp=Get-NetTCPConnection -LocalPort 9085 -State Listen -ErrorAction SilentlyContinue;" ^
    "if($tcp){exit 1}else{exit 0}"

if errorlevel 1 (
    echo.
    echo ERROR: Port 9085 is still occupied by another process.
    echo.
    pause
    endlocal
    exit /b 1
)

echo.
echo Starting WatchParty locally on port 9085...
start "WatchParty Server" cmd /k "cd /d "%ROOT%" && node server.js"

echo Waiting for WatchParty to become ready...

:wait
curl.exe -fsS --max-time 1 http://127.0.0.1:9085/ >nul 2>&1
if not errorlevel 1 goto :ready

timeout /t 1 /nobreak >nul
goto :wait

:ready

del /q "%RUNTIME%\local.active" >nul 2>&1
del /q "%RUNTIME%\lan.active" >nul 2>&1
echo active> "%RUNTIME%\local.active"

echo.
echo Local WatchParty is ready.
echo.
echo Local entry: http://127.0.0.1:9085/
echo Local canonical: http://127-0-0-1.sslip.io:9085/
echo Local mode is loopback-only. The sslip.io hostname resolves back to 127.0.0.1 and is NOT a LAN share URL.
echo Local room links use the canonical loopback hostname so YouTube embeds can load without enabling LAN mode.
echo.
echo Keep the WatchParty server window open while Local access is needed.
echo.
pause

endlocal
exit /b 0
