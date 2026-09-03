@echo off
setlocal
cd /d "%~dp0\.."
set "PYTHON=.\.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
    echo UMDF_SMOKE FAIL reason=python_venv_missing
    exit /b 1
)
"%PYTHON%" tools\umdf_installed_smoke.py --quiet
exit /b %errorlevel%
