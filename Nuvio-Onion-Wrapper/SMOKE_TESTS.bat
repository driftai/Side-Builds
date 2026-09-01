@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Nuvio Onion Wrapper - Smoke Tests
set "RC=0"

where py >nul 2>nul
if not errorlevel 1 (
  py -3 "%~dp0smoke_tests.py"
  if errorlevel 1 set "RC=1"
  py -3 -m pytest "%~dp0tests\test_security.py" -q
  if errorlevel 1 set "RC=1"
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python 3 is required for smoke tests.
    pause
    exit /b 1
  )
  python "%~dp0smoke_tests.py"
  if errorlevel 1 set "RC=1"
  python -m pytest "%~dp0tests\test_security.py" -q
  if errorlevel 1 set "RC=1"
)

echo.
if "%RC%"=="0" (echo Functional + security smoke tests passed.) else (echo Smoke tests found failures. See output above.)
pause
exit /b %RC%
