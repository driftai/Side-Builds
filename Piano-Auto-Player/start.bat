@echo off
setlocal
cd /d "%~dp0"

echo.
echo  Piano Auto Player
echo  -----------------
echo.

where py >nul 2>nul
if %errorlevel%==0 (
  set "PY=py -3"
) else (
  set "PY=python"
)

echo Starting on http://127.0.0.1:8765
start "" "http://127.0.0.1:8765"
%PY% run.py
if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
echo Startup failed. Make sure Python 3 is installed and available in PATH.
pause
exit /b 1
