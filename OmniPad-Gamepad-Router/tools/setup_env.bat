@echo off
setlocal
title OmniPad Environment Setup
cd /d "%~dp0\.."

echo =======================================================
echo   Setting up OmniPad Gamepad Router Environment
echo =======================================================

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment ^(.venv^)...
    python --version >nul 2>&1
    if errorlevel 1 (
        py -3 --version >nul 2>&1
        if errorlevel 1 (
            echo ERROR: Python 3 was not found. Install Python 3 and ensure python or py is on PATH.
            exit /b 1
        )
        py -3 -m venv .venv
    ) else (
        python -m venv .venv
    )
    if errorlevel 1 (
        echo ERROR: Failed to create the OmniPad virtual environment.
        exit /b 1
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Virtual environment Python was not created at .venv\Scripts\python.exe.
    exit /b 1
)

echo Updating Python packaging tools...
".\.venv\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :dependency_failure

echo Installing dependencies from requirements.txt...
".\.venv\Scripts\python.exe" -m pip install -r requirements.txt --no-warn-script-location
if errorlevel 1 goto :dependency_failure

echo Verifying vgamepad installation...
".\.venv\Scripts\python.exe" -c "import vgamepad" 2>nul
if errorlevel 1 (
    echo Installing vgamepad...
    set "VGAMEPAD_SKIP_VIGEMBUS_INSTALL=true"
    ".\.venv\Scripts\python.exe" -m pip install vgamepad --no-build-isolation
    if errorlevel 1 (
        echo ERROR: Failed to install vgamepad.
        exit /b 1
    )
    ".\.venv\Scripts\python.exe" -c "import vgamepad" 2>nul
    if errorlevel 1 (
        echo ERROR: vgamepad installed but could not be imported.
        exit /b 1
    )
)

echo Setup completed successfully!
exit /b 0

:dependency_failure
echo ERROR: Failed to install OmniPad Python dependencies.
exit /b 1
