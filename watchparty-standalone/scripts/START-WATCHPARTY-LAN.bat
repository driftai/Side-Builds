@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

set "ROOT=%CD%"
set "RUNTIME=%ROOT%\.runtime"
set "SERVERPIDFILE=%RUNTIME%\lan-server.pid"

title WatchParty Standalone - LAN

echo.
echo Starting WatchParty Standalone for local LAN access...
echo Devices on the same Wi-Fi can use the LAN address shown below.
echo.

if not exist "%ROOT%\server.js" (
    echo ERROR: server.js was not found.
    echo.
    pause
    exit /b 1
)

if exist "%RUNTIME%\remote-url.txt" (
    echo.
    echo WatchParty Remote is currently active.
    echo Stop Remote before starting LAN mode.
    echo.
    pause
    exit /b 1
)

call "%ROOT%\scripts\SYNC-WATCHPARTY-STATE.bat"

if exist "%RUNTIME%\local.active" (
    echo.
    echo WatchParty Local is currently active.
    echo Stop Local before starting LAN mode.
    echo.
    pause
    exit /b 1
)

if exist "%RUNTIME%\lan.active" (
    echo.
    echo LAN mode is already active.
    echo.
    pause
    exit /b 0
)

REM ============================================================
REM Remove stale WatchParty Node server if needed.
REM ============================================================

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

REM ============================================================
REM Port must be free before starting.
REM ============================================================

powershell.exe -NoProfile -Command ^
    "$tcp=Get-NetTCPConnection -LocalPort 9085 -State Listen -ErrorAction SilentlyContinue; if($tcp){exit 1}else{exit 0}"

if errorlevel 1 (
    echo.
    echo ERROR: Port 9085 is still occupied.
    echo.
    pause
    exit /b 1
)

if not exist "%RUNTIME%" mkdir "%RUNTIME%" >nul 2>&1

del /q "%RUNTIME%\local.active" >nul 2>&1
del /q "%RUNTIME%\lan.active" >nul 2>&1
del /q "%SERVERPIDFILE%" >nul 2>&1

REM ============================================================
REM Launch a REAL reusable command terminal.
REM When Node is stopped, this shell remains open.
REM ============================================================

echo.
echo Starting WatchParty server with LAN binding...
echo.

start "WatchParty Server - LAN" cmd /k "cd /d "%ROOT%" && node server.js --lan"

echo Waiting for the WatchParty LAN server to become ready...
echo.

set /a TRIES=0

:wait
set /a TRIES+=1

REM Find the actual LAN Node process.
powershell.exe -NoProfile -Command ^
    "$p=Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.Name -eq 'node.exe' -and [string]$_.CommandLine -match 'server\.js' -and [string]$_.CommandLine -match '(?i)(^|\s)--lan(\s|$)' } | Select-Object -First 1; if($p){ $p.ProcessId | Set-Content -Encoding ASCII '%SERVERPIDFILE%'; exit 0 }else{ exit 1 }"

if errorlevel 1 (
    if %TRIES% GEQ 30 goto :failed
    timeout /t 1 /nobreak >nul
    goto :wait
)

set /p SERVERPID=<"%SERVERPIDFILE%"

REM Verify that THIS LAN Node process owns the wildcard listener.
powershell.exe -NoProfile -Command ^
    "$tcp=Get-NetTCPConnection -LocalPort 9085 -State Listen -ErrorAction SilentlyContinue; $match=$tcp | Where-Object { $_.OwningProcess -eq %SERVERPID% -and ($_.LocalAddress -eq '0.0.0.0' -or $_.LocalAddress -eq '::') }; if($match){exit 0}else{exit 1}"

if errorlevel 1 (
    if %TRIES% GEQ 30 goto :failed
    timeout /t 1 /nobreak >nul
    goto :wait
)

echo active> "%RUNTIME%\lan.active"

echo.
echo ============================================================
echo WatchParty LAN server is ready.
echo Node PID: %SERVERPID%
echo ============================================================
echo.

echo LAN addresses:
powershell.exe -NoProfile -Command ^
  "$items=Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notlike '169.254.*' -and $_.IPAddress -ne '127.0.0.1' -and $_.PrefixOrigin -ne 'WellKnown' }; $physical=$items | Where-Object { $_.InterfaceAlias -notmatch '(?i)virtual|vEthernet|Hyper-V|WSL|Docker|VMware|VirtualBox|VPN|Tailscale|WireGuard|ZeroTier|Hamachi|Host-Only|NAT' }; $preferred=($physical | Select-Object -First 1 -ExpandProperty IPAddress); if($preferred){ $dash=$preferred -replace '\.', '-'; Write-Host ('LAN IP entry:      http://' + $preferred + ':9085/  [redirects to canonical LAN HOST for YouTube compatibility]'); Write-Host ('LAN HOST:          http://' + $dash + '.sslip.io:9085/'); Write-Host ('LAN SHARE HOST:    http://' + $dash + '.sslip.io:9085/') } else { Write-Host 'LAN IP: unavailable' }"

echo.
echo RETIRED / NOT CROSS-DEVICE:
echo   http://192.168.128.1:9085/
echo   http://192-168-128-1.sslip.io:9085/
echo These WSL/Hyper-V virtual-adapter URLs are host-only diagnostics and are NOT LAN share URLs.

echo.
echo Local: http://127.0.0.1:9085/
echo LAN sharing uses the canonical physical LAN sslip.io hostname.
echo The canonical sslip.io LAN HOST is the cross-device share URL; it requires DNS access.
echo Raw physical LAN IP entry points are redirected to the canonical sslip.io host so YouTube embeds load correctly.
echo.
echo The WatchParty server terminal remains reusable after Stop LAN.
echo.
pause

endlocal
exit /b 0

:failed
echo.
echo ERROR: WatchParty LAN server did not become ready.
echo.
pause
endlocal
exit /b 1
