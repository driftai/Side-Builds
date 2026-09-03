@echo off
setlocal
title Build OmniPad Virtual Keyboard HID Driver
pushd "%~dp0"

echo ============================================================
echo   Building OmniPad Virtual Keyboard Driver (x64 Debug)
echo ============================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build-driver.ps1"
if errorlevel 1 (
    echo [ERROR] Driver compilation failed.
    popd
    exit /b 1
)

echo.
echo ============================================================
echo   Driver Build Successful!
echo   Package: x64\Debug\OmniPadVirtualKeyboard
echo ============================================================
popd
exit /b 0
