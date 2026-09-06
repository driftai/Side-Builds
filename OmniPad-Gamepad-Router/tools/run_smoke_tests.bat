@echo off
setlocal
title OmniPad Smoke Tests
cd /d "%~dp0\.."
set "PYTHON=.\.venv\Scripts\python.exe"

if not exist "%PYTHON%" goto :run_setup
"%PYTHON%" -c "import fastapi, uvicorn, vgamepad" >nul 2>&1
if errorlevel 1 goto :run_setup
goto :run_tests

:run_setup
call tools\setup_env.bat
if errorlevel 1 goto :setup_failed
if not exist "%PYTHON%" goto :setup_failed
"%PYTHON%" -c "import fastapi, uvicorn, vgamepad" >nul 2>&1
if errorlevel 1 goto :setup_failed

:run_tests
"%PYTHON%" tools\run_smoke_tests.py %*
exit /b %ERRORLEVEL%

:setup_failed
echo FAIL smoke: OmniPad environment setup failed; tests were not started.
exit /b 1
