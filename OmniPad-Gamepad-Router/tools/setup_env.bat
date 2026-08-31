@echo off
title OmniPad Environment Setup
cd /d "%~dp0\.."

echo =======================================================
echo   Setting up OmniPad Gamepad Router Environment
echo =======================================================

if not exist ".venv" (
    echo Creating virtual environment (.venv)...
    python -m venv .venv
)

echo Installing dependencies from requirements.txt...
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt --no-warn-script-location

echo Verifying vgamepad installation...
.\.venv\Scripts\python.exe -c "import vgamepad" 2>nul
if %errorlevel% neq 0 (
    echo Installing vgamepad...
    set VGAMEPAD_SKIP_VIGEMBUS_INSTALL=true
    set VGAMEPAD_SKIP_INSTALL=true
    .\.venv\Scripts\python.exe -m pip install vgamepad --no-build-isolation
)

echo Setup completed successfully!
pause
