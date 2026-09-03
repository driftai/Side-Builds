@echo off
setlocal
title OmniPad Install and Repair
cd /d "%~dp0"
set "REPAIR_SCRIPT=tools\install_or_repair.ps1"

:menu
cls
echo ======================================================================
echo                 OMNIPAD INSTALL / REPAIR
echo ======================================================================
echo   [1] Show component readiness ^(no changes^)
echo   [2] Install/repair all normal runtime features
echo       Python environment, ViGEmBus, local cloudflared, and UMDF keyboard
echo   [3] Install/repair core router only ^(skip UMDF keyboard trust/device^)
echo   [0] Return
echo.
echo   Developer-only VHF/WDK files are preserved but are not installed here.
echo ======================================================================
set /p repair_opt="Select an option: "

if "%repair_opt%"=="1" goto status
if "%repair_opt%"=="2" goto repair_all
if "%repair_opt%"=="3" goto repair_core
if "%repair_opt%"=="0" exit /b 0
goto invalid

:status
powershell -NoProfile -ExecutionPolicy Bypass -File "%REPAIR_SCRIPT%" -Action Status
pause
goto menu

:repair_all
echo.
echo This exact repair scope may:
echo   - stop this repository's running OmniPad server before changing files
echo   - install Python 3.12 for the current user through Windows Package Manager
echo   - create/update this repository's ignored .venv
echo   - install the signed ViGEmBus MSI bundled by vgamepad if missing
echo   - download the signed cloudflared executable into ignored .runtime\bin
echo   - trust the bundled OmniPad development certificate and install/update
echo     only Root\OmniPadVirtualKeyboardUmdf
echo.
echo It will NOT change Test Mode, BCD, Secure Boot, install WDK/Visual Studio,
echo install cloudflared as a service, or alter the physical keyboard.
choice /C YN /N /M "Continue (UAC appears only if a system driver needs repair)? [Y/N]: "
if errorlevel 2 goto menu
powershell -NoProfile -ExecutionPolicy Bypass -File "%REPAIR_SCRIPT%" -Action RepairAll -Confirmed
pause
goto menu

:repair_core
echo.
echo This repairs Python, repository packages, ViGEmBus, and local cloudflared.
echo It stops only this repository's running server first. It does not touch the
echo UMDF keyboard device/certificate, boot mode, or developer toolchains.
choice /C YN /N /M "Continue (UAC appears only if ViGEmBus is missing)? [Y/N]: "
if errorlevel 2 goto menu
powershell -NoProfile -ExecutionPolicy Bypass -File "%REPAIR_SCRIPT%" -Action RepairCore -Confirmed
pause
goto menu

:invalid
echo Invalid selection.
timeout /t 1 >nul
goto menu
