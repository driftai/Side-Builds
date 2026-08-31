@echo off
setlocal enabledelayedexpansion
title OmniPad Gamepad and Keyboard Router Control Center
cd /d "%~dp0"

:menu
cls
echo ======================================================================
echo    OMNIPAD GAMEPAD ^& KEYBOARD ROUTER -- CONTROL CENTER v1.1.2
echo ======================================================================
echo.
echo   [1] Start Router (Cloudflare Quick Tunnel - Cross-City Play)
echo   [2] Start Router (Local LAN Only - Same Wi-Fi / Low Latency)
echo   [3] Start Router (Custom Port / Arguments)
echo   ------------------------------------------------------------------
echo   [4] Run All Automated Smoke ^& Diagnostic Tests (9 Test Suites)
echo   [5] Run Raw Input Hardware Keyboard Diagnostic Tool
echo   [6] Build ^& Install VHF Virtual Keyboard Driver (Developer)
echo   ------------------------------------------------------------------
echo   [7] Clean Up Lingering Processes (cloudflared, orphaned servers)
echo   [0] Exit
echo.
echo ======================================================================
set /p opt="Select an option [0-7]: "

if "%opt%"=="1" goto start_tunnel
if "%opt%"=="2" goto start_lan
if "%opt%"=="3" goto start_custom
if "%opt%"=="4" goto run_tests
if "%opt%"=="5" goto run_raw_input
if "%opt%"=="6" goto install_driver
if "%opt%"=="7" goto cleanup
if "%opt%"=="0" goto exit_app

echo Invalid selection. Please try again.
timeout /t 2 >nul
goto menu

:start_tunnel
cls
echo Starting OmniPad with Cloudflare Quick Tunnel...
call tools\start_with_tunnel.bat
goto menu

:start_lan
cls
echo Starting OmniPad in Local LAN Mode (Port 8000)...
call tools\start_router.bat
goto menu

:start_custom
cls
set /p custom_port="Enter port number (default 8000): "
if "%custom_port%"=="" set custom_port=8000
set /p custom_tunnel="Enable Cloudflare tunnel? (y/n, default n): "
if /i "%custom_tunnel%"=="y" (
    .\.venv\Scripts\python.exe server.py --port %custom_port% --tunnel
) else (
    .\.venv\Scripts\python.exe server.py --port %custom_port%
)
taskkill /F /IM cloudflared.exe 2>nul
pause
goto menu

:run_tests
cls
echo Running Full OmniPad Diagnostic and Smoke Test Suites...
call tools\run_smoke_tests.bat
goto menu

:run_raw_input
cls
echo Running Windows Raw Input Keyboard Enumeration Tool...
.\.venv\Scripts\python.exe tools\enumerate_raw_input_keyboards.py
pause
goto menu

:install_driver
cls
echo Installing / Building OmniPad VHF Keyboard Kernel Driver...
call drivers\virtual-keyboard\build-driver.bat
pause
goto menu

:cleanup
cls
call tools\cleanup_stragglers.bat
pause
goto menu

:exit_app
cls
taskkill /F /IM cloudflared.exe 2>nul
echo Goodbye!
exit /b 0
