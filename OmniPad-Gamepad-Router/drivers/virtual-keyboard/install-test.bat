@echo off
setlocal
title Install OmniPad Virtual Keyboard HID Driver
pushd "%~dp0"

echo ============================================================
echo   Installing OmniPad Virtual Keyboard Driver (Test Sign Mode)
echo ============================================================
echo.
echo NOTE: Installing a kernel driver requires Administrator privileges.
echo The package must already be signed and trusted. Secure Boot,
echo Test Mode, certificate trust, and reboot are not changed here.
echo.

net session >nul 2>&1
if errorlevel 1 (
    echo [ERROR] This script must be run as Administrator.
    popd
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-driver.ps1"
if errorlevel 1 (
    echo [ERROR] Driver installation failed.
    popd
    exit /b 1
)

echo.
echo [SUCCESS] OmniPad Virtual Keyboard driver installed!
popd
exit /b 0
