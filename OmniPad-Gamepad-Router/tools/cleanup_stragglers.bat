@echo off
setlocal
title OmniPad Process Cleanup
cd /d "%~dp0\.."
echo This cleanup targets only Python servers launched from:
echo   %CD%\server.py
echo and only their child processes.
choice /C YN /N /M "Continue? [Y/N]: "
if errorlevel 2 exit /b 0
powershell -NoProfile -ExecutionPolicy Bypass -File "tools\manage_router.ps1" -Action Cleanup -Confirmed
exit /b %ERRORLEVEL%
