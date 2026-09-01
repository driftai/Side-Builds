@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title WatchParty Standalone

:menu
cls

call "%~dp0scripts\SYNC-WATCHPARTY-STATE.bat"

set "RUNTIME=%~dp0.runtime"

if exist "%RUNTIME%\local.active" (
    set "LOCAL_LABEL=Stop Local"
) else (
    set "LOCAL_LABEL=Start Local"
)

if exist "%RUNTIME%\lan.active" (
    set "LAN_LABEL=Stop LAN"
) else (
    set "LAN_LABEL=Start LAN"
)

if exist "%RUNTIME%\remote-url.txt" (
    set "REMOTE_LABEL=Stop Remote"
) else (
    set "REMOTE_LABEL=Start Remote"
)

echo =====================================================
echo                 WATCHPARTY STANDALONE
echo =====================================================
echo.
echo  [1] %LOCAL_LABEL%
echo  [2] %LAN_LABEL%
echo  [3] %REMOTE_LABEL% (Cloudflare Quick Tunnel)
echo  [4] Stop Remote
echo  [5] Organize / Cleanup Project
echo  [6] Open Project Folder
echo  [7] Exit
echo.
set "OPTION="
set /p "OPTION=Select an option: "

if "%OPTION%"=="1" goto :localtoggle
if "%OPTION%"=="2" goto :lantoggle
if "%OPTION%"=="3" goto :remote
if "%OPTION%"=="4" goto :stopremote
if "%OPTION%"=="5" goto :maintain
if "%OPTION%"=="6" goto :open
if "%OPTION%"=="7" goto :exit

echo.
echo Invalid option. Please enter 1-7.
timeout /t 1 /nobreak >nul
goto :menu

:localtoggle
call "%~dp0scripts\SYNC-WATCHPARTY-STATE.bat"

if exist "%~dp0.runtime\local.active" (
    call "%~dp0scripts\STOP-WATCHPARTY-LOCAL.bat"
) else (
    call "%~dp0scripts\START-WATCHPARTY-LOCAL.bat"
)
goto :menu

:lantoggle
call "%~dp0scripts\SYNC-WATCHPARTY-STATE.bat"

if exist "%~dp0.runtime\lan.active" (
    call "%~dp0scripts\STOP-WATCHPARTY-LAN.bat"
) else (
    call "%~dp0scripts\START-WATCHPARTY-LAN.bat"
)
goto :menu

:remote
start "WatchParty Remote Monitor" cmd /k call "%~dp0scripts\START-WATCHPARTY-REMOTE.bat"
goto :menu

:stopremote
call "%~dp0scripts\STOP-WATCHPARTY-REMOTE.bat"
goto :menu

:maintain
call "%~dp0scripts\MAINTAIN-WATCHPARTY.bat"
goto :menu

:open
start "" explorer.exe "%~dp0"
goto :menu

:exit
endlocal
exit /b 0
