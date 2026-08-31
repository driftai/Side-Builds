@echo off
setlocal
title Build OmniPad Virtual Keyboard HID Driver
pushd "%~dp0"

echo ============================================================
echo   Building OmniPad Virtual Keyboard Driver (x64 Release/Debug)
echo ============================================================
echo.

set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSWHERE%" goto no_vswhere

set "VSINSTALL="
for /f "usebackq tokens=*" %%i in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath 2^>nul`) do (
    set "VSINSTALL=%%i"
)

if "%VSINSTALL%"=="" goto no_toolchain

set "MSBUILD=%VSINSTALL%\MSBuild\Current\Bin\MSBuild.exe"
if not exist "%MSBUILD%" goto no_msbuild

echo Using MSBuild: "%MSBUILD%"
"%MSBUILD%" OmniPadVirtualKeyboard.sln /m /p:Configuration=Release /p:Platform=x64 /p:SignMode=Off
if errorlevel 1 (
    echo [WARNING] Release build failed. Attempting Debug build...
    "%MSBUILD%" OmniPadVirtualKeyboard.sln /m /p:Configuration=Debug /p:Platform=x64 /p:SignMode=Off
)

if errorlevel 1 (
    echo [ERROR] Driver compilation failed.
    popd
    exit /b 1
)

echo.
echo ============================================================
echo   Driver Build Successful!
echo   Output located in x64\Release or x64\Debug
echo ============================================================
popd
exit /b 0

:no_vswhere
echo [INFO] Visual Studio / WDK build tools not detected.
echo The virtual keyboard kernel driver is an optional developer build
echo and is only needed if you want a dedicated hardware HID device
echo for Raw Input game separation.
echo.
echo OmniPad already works out-of-the-box using:
echo   - Xbox 360 (ViGEmBus) for It Takes Two / Gamepad co-op
echo   - Keyboard 2 (Target-Locked SendInput) for 2P Keyboard titles
echo.
popd
exit /b 0

:no_toolchain
echo [INFO] Visual Studio C++ toolchain not found.
echo Install Visual Studio with "Desktop development with C++" and WDK to build kernel drivers.
popd
exit /b 0

:no_msbuild
echo [INFO] MSBuild not found at: "%MSBUILD%"
popd
exit /b 0
