@echo off
setlocal
title OmniPad Gamepad Router
cd /d "%~dp0\.."
set "PYTHON=.\.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo Virtual environment not found. Running setup...
    goto :run_setup
)

"%PYTHON%" -c "import fastapi, uvicorn, vgamepad" >nul 2>&1
if errorlevel 1 (
    echo OmniPad environment incomplete. Running setup...
    goto :run_setup
)
goto :start_router

:run_setup
call tools\setup_env.bat
if errorlevel 1 goto :setup_failed
if not exist "%PYTHON%" goto :setup_failed
"%PYTHON%" -c "import fastapi, uvicorn, vgamepad" >nul 2>&1
if errorlevel 1 goto :setup_failed

:start_router
echo Starting OmniPad Gamepad Router...
"%PYTHON%" server.py %*
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" echo OmniPad exited with code %EXIT_CODE%.
pause
exit /b %EXIT_CODE%

:setup_failed
echo.
echo ERROR: OmniPad environment setup failed. The router was not started.
pause
exit /b 1
