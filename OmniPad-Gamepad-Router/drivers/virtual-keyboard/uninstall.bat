@echo off
setlocal
title Remove OmniPad Virtual Keyboard HID Driver
pushd "%~dp0"

echo ============================================================
echo   Removing OmniPad Virtual Keyboard Driver
echo ============================================================
echo.

net session >nul 2>&1
if errorlevel 1 (
    echo [ERROR] This script must be run as Administrator.
    popd
    exit /b 1
)

powershell -ExecutionPolicy Bypass -File "%~dp0remove-driver.ps1"
if errorlevel 1 (
    echo [ERROR] Driver removal failed.
    popd
    exit /b 1
)

echo.
echo [SUCCESS] OmniPad Virtual Keyboard driver removed cleanly.
popd
exit /b 0
