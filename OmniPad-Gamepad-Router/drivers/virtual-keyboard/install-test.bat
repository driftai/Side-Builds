@echo off
setlocal
title Install OmniPad Virtual Keyboard HID Driver
pushd "%~dp0"

echo ============================================================
echo   Installing OmniPad Virtual Keyboard Driver (Test Sign Mode)
echo ============================================================
echo.
echo NOTE: Installing a kernel driver requires Administrator privileges.
echo Windows 64-bit also requires test-signing mode enabled:
echo   bcdedit /set testsigning on  (requires system reboot)
echo.

net session >nul 2>&1
if errorlevel 1 (
    echo [ERROR] This script must be run as Administrator.
    popd
    exit /b 1
)

if not exist "%~dp0x64\Release\OmniPadVirtualKeyboard.sys" if not exist "%~dp0x64\Debug\OmniPadVirtualKeyboard.sys" (
    echo [INFO] Compiled driver binary not found.
    echo Please build the driver first using Option 6 (build-driver.bat).
    popd
    exit /b 0
)

powershell -ExecutionPolicy Bypass -File "%~dp0install-driver.ps1"
if errorlevel 1 (
    echo [ERROR] Driver installation failed.
    popd
    exit /b 1
)

echo.
echo [SUCCESS] OmniPad Virtual Keyboard driver installed!
popd
exit /b 0
