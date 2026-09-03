@echo off
setlocal enabledelayedexpansion
title OmniPad Router Control Center
cd /d "%~dp0"
set "ROUTER_MANAGER=tools\manage_router.ps1"
set "UMDF_MANAGER=drivers\virtual-keyboard-umdf\manage-driver.ps1"

:menu
cls
echo ======================================================================
echo              OMNIPAD ROUTER -- CONTROL CENTER v1.3
echo ======================================================================
echo.
echo   ROUTER
echo   [1] Start Cloudflare + LAN router
echo   [2] Start LAN-only router
echo   [3] Start with custom port
echo   [4] Show status, URLs, room code, and logs
echo   [5] Open host dashboard
echo   [6] Start Cloudflare tunnel on running router
echo   [7] Stop Cloudflare tunnel only (keep LAN online)
echo   [8] Panic release all virtual inputs
echo   [9] Stop router, tunnel, helper, and all routed input
echo.
echo   TOOLS
echo   [I] Install/repair and show component readiness
echo   [D] Diagnostics and smoke tests
echo   [K] Virtual keyboard management
echo   [C] Scoped cleanup for this OmniPad repository
echo   [0] Exit control center (leave current router state unchanged)
echo.
echo ======================================================================
set /p opt="Select an option: "

if /i "%opt%"=="1" goto start_tunnel
if /i "%opt%"=="2" goto start_lan
if /i "%opt%"=="3" goto start_custom
if /i "%opt%"=="4" goto router_status
if /i "%opt%"=="5" goto open_dashboard
if /i "%opt%"=="6" goto tunnel_start
if /i "%opt%"=="7" goto tunnel_stop
if /i "%opt%"=="8" goto panic
if /i "%opt%"=="9" goto router_stop
if /i "%opt%"=="I" goto install_repair
if /i "%opt%"=="D" goto diagnostics
if /i "%opt%"=="K" goto keyboard
if /i "%opt%"=="C" goto cleanup
if /i "%opt%"=="0" exit /b 0
goto invalid

:start_tunnel
call tools\start_with_tunnel.bat
pause
goto menu

:start_lan
call tools\start_router.bat
pause
goto menu

:start_custom
set "custom_port=8000"
set /p custom_port="Port [8000]: "
if "%custom_port%"=="" set "custom_port=8000"
set "custom_mode=lan"
set /p tunnel_choice="Enable Cloudflare tunnel? [y/N]: "
if /i "%tunnel_choice%"=="y" set "custom_mode=tunnel"
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROUTER_MANAGER%" -Action Start -Mode "%custom_mode%" -Port "%custom_port%"
pause
goto menu

:router_status
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROUTER_MANAGER%" -Action Status
pause
goto menu

:open_dashboard
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROUTER_MANAGER%" -Action OpenDashboard
pause
goto menu

:tunnel_start
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROUTER_MANAGER%" -Action StartTunnel
pause
goto menu

:tunnel_stop
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROUTER_MANAGER%" -Action StopTunnel
pause
goto menu

:panic
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROUTER_MANAGER%" -Action Panic
pause
goto menu

:router_stop
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROUTER_MANAGER%" -Action Stop
pause
goto menu

:install_repair
call install_or_repair.bat
goto menu

:diagnostics
cls
echo ======================================================================
echo                       DIAGNOSTICS
echo ======================================================================
echo   [1] Run full architecture + automated smoke suite
echo   [2] Run concise installed UMDF keyboard smoke
echo   [3] Enumerate physical and virtual Raw Input keyboards
echo   [4] Run architecture gate only
echo   [0] Back
set /p diag="Select an option: "
if "%diag%"=="1" call tools\run_smoke_tests.bat
if "%diag%"=="2" call tools\run_umdf_installed_smoke.bat
if "%diag%"=="3" .\.venv\Scripts\python.exe tools\enumerate_raw_input_keyboards.py
if "%diag%"=="4" .\.venv\Scripts\python.exe tools\check_architecture.py
if "%diag%"=="0" goto menu
pause
goto diagnostics

:keyboard
cls
echo ======================================================================
echo                 VIRTUAL KEYBOARD MANAGEMENT
echo ======================================================================
echo   [1] Show UMDF virtual keyboard status
echo   [2] Install/repair bundled normal-mode UMDF keyboard
echo   [3] Remove UMDF device and its exact local trust certificate
echo   [4] Run real installed-device keyboard smoke
echo   [5] Developer rebuild, sign, and install UMDF keyboard
echo   [6] Build preserved VHF source package only (future signing path)
echo   [0] Back
set /p keyopt="Select an option: "
if "%keyopt%"=="1" goto umdf_status
if "%keyopt%"=="2" goto umdf_install
if "%keyopt%"=="3" goto umdf_remove
if "%keyopt%"=="4" goto umdf_smoke
if "%keyopt%"=="5" goto umdf_rebuild
if "%keyopt%"=="6" goto vhf_build
if "%keyopt%"=="0" goto menu
goto keyboard_invalid

:umdf_status
powershell -NoProfile -ExecutionPolicy Bypass -File "%UMDF_MANAGER%" -Action Status
pause
goto keyboard

:umdf_install
echo.
echo This will verify the bundled UMDF package, trust only:
echo   CN=OmniPad Local UMDF Development
echo and install/update only:
echo   Root\OmniPadVirtualKeyboardUmdf
echo Visual Studio, WDK, DevCon, Test Mode, and a reboot are not required.
echo It will not change Test Mode, BCD, Secure Boot, or the physical keyboard.
choice /C YN /N /M "Continue? [Y/N]: "
if errorlevel 2 goto keyboard
powershell -NoProfile -ExecutionPolicy Bypass -File "%UMDF_MANAGER%" -Action Install -Confirmed
pause
goto keyboard

:umdf_rebuild
echo.
echo DEVELOPER PATH: this requires Visual Studio C++ Build Tools and the WDK.
echo It rebuilds, creates/trusts a machine-local certificate, and installs only:
echo   Root\OmniPadVirtualKeyboardUmdf
echo It does not change Test Mode, BCD, Secure Boot, or the physical keyboard.
choice /C YN /N /M "Continue with developer rebuild? [Y/N]: "
if errorlevel 2 goto keyboard
powershell -NoProfile -ExecutionPolicy Bypass -File "%UMDF_MANAGER%" -Action RebuildInstall -Confirmed
pause
goto keyboard

:umdf_remove
echo.
echo This removes only Root\OmniPadVirtualKeyboardUmdf and the exact
echo CN=OmniPad Local UMDF Development certificate. Source and build scripts stay.
set /p remove_confirm="Type REMOVE UMDF to continue: "
if /i not "%remove_confirm%"=="REMOVE UMDF" (
    echo Removal canceled.
    pause
    goto keyboard
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%UMDF_MANAGER%" -Action Remove -Confirmed
pause
goto keyboard

:umdf_smoke
call tools\run_umdf_installed_smoke.bat
pause
goto keyboard

:vhf_build
echo Building preserved VHF source only. This does not install or change boot mode.
call drivers\virtual-keyboard\build-driver.bat
pause
goto keyboard

:cleanup
echo This stops only Python server processes whose command line points to:
echo   %CD%\server.py
echo It also stops only their child processes. Other Python and Cloudflare jobs remain untouched.
choice /C YN /N /M "Run scoped cleanup? [Y/N]: "
if errorlevel 2 goto menu
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROUTER_MANAGER%" -Action Cleanup -Confirmed
pause
goto menu

:keyboard_invalid
echo Invalid keyboard option.
timeout /t 1 >nul
goto keyboard

:invalid
echo Invalid selection.
timeout /t 1 >nul
goto menu
