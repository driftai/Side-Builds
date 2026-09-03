@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build-driver.ps1"
exit /b %errorlevel%
