@echo off
setlocal EnableExtensions
title Local MoE Harness Setup
set "ROOT=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\setup-windows.ps1"
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" (
  echo Setup failed. Review the messages above.
) else (
  echo Setup completed successfully.
  echo Run Control.bat to start the harness.
)
pause
exit /b %RC%
