@echo off
setlocal EnableExtensions
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (py -3 "%~dp0configure_nuvio.py" & goto :done)
where python >nul 2>nul
if not errorlevel 1 (python "%~dp0configure_nuvio.py" & goto :done)
echo ERROR: Python 3 not found on PATH.
:done
pause
