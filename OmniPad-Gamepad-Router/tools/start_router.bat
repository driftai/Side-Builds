@echo off
setlocal
title OmniPad Gamepad Router
cd /d "%~dp0\.."

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Running setup...
    call tools\setup_env.bat
    if errorlevel 1 goto :setup_failed
)

if not exist ".venv\Scripts\python.exe" goto :setup_failed

echo Starting OmniPad Gamepad Router...
".\.venv\Scripts\python.exe" server.py %*
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" echo OmniPad exited with code %EXIT_CODE%.
pause
exit /b %EXIT_CODE%

:setup_failed
echo.
echo ERROR: OmniPad environment setup failed. The router was not started.
pause
exit /b 1
