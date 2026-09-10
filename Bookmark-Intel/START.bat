@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  py -3 -m venv .venv 2>nul || python -m venv .venv
  if errorlevel 1 goto :fail
)

echo Installing/updating requirements...
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
if errorlevel 1 goto :fail

echo.
echo Browser fallbacks:
where lightpanda >nul 2>nul
if errorlevel 1 (
  echo   Lightpanda: not found on PATH - optional
) else (
  echo   Lightpanda: available
)

".venv\Scripts\python.exe" -c "import camoufox" >nul 2>nul
if errorlevel 1 (
  echo   Camoufox: Python package unavailable
) else (
  echo   Camoufox: Python package available
  ".venv\Scripts\python.exe" -m camoufox path >nul 2>nul
  if errorlevel 1 echo   Camoufox browser binary may need: .venv\Scripts\python.exe -m camoufox fetch
)

echo.
echo Starting Bookmark Intel POC at http://127.0.0.1:9077
start "" http://127.0.0.1:9077
".venv\Scripts\python.exe" server.py --serve --host 127.0.0.1 --port 9077
exit /b %errorlevel%

:fail
echo.
echo Setup failed. Make sure Python 3 is installed and available as py or python.
pause
exit /b 1
