@echo off
title OmniPad Gamepad Router
cd /d "%~dp0\.."

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Running setup...
    call tools\setup_env.bat
)

echo Starting OmniPad Gamepad Router...
.\.venv\Scripts\python.exe server.py %*
pause
