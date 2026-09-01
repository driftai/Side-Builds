@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Nuvio Onion Wrapper

rem Usage:
rem   START_WRAPPER.bat                    -> use/install Nuvio at .\nuvio
rem   START_WRAPPER.bat "D:\Apps\Nuvio" -> use/install Nuvio anywhere on disk
rem   set NUVIO_PATH=D:\Apps\Nuvio     -> use a custom location

set "NUVIO_DIR=%~1"
if not defined NUVIO_DIR if defined NUVIO_PATH set "NUVIO_DIR=%NUVIO_PATH%"
if not defined NUVIO_DIR set "NUVIO_DIR=%~dp0nuvio"
for %%I in ("%NUVIO_DIR%") do set "NUVIO_DIR=%%~fI"

rem A folder existing is not enough. The source install must contain the
rem upstream files required to build and run Nuvio.
set "NUVIO_MISSING=0"
if not exist "%NUVIO_DIR%\package.json" set "NUVIO_MISSING=1"
if not exist "%NUVIO_DIR%\appinfo.json" set "NUVIO_MISSING=1"
if not exist "%NUVIO_DIR%\index.html" set "NUVIO_MISSING=1"
if not exist "%NUVIO_DIR%\js\app.js" set "NUVIO_MISSING=1"

if "%NUVIO_MISSING%"=="1" (
  echo.
  echo Nuvio is missing or incomplete at:
  echo   %NUVIO_DIR%
  echo.
  echo Running the Nuvio installer/repair step...
  echo.
  call "%~dp0GET_NUVIO.bat" "%NUVIO_DIR%"
  if errorlevel 1 (
    echo.
    echo Nuvio installation/repair failed.
    pause
    exit /b 1
  )
)

if not exist "%NUVIO_DIR%\dist\index.html" goto :BUILD
if not exist "%NUVIO_DIR%\dist\app.bundle.js" goto :BUILD
if not exist "%NUVIO_DIR%\dist\core-js.bundle.js" goto :BUILD
if not exist "%NUVIO_DIR%\dist\nuvio.env.js" goto :BUILD
goto :READY

:BUILD
echo.
echo Nuvio browser build missing. Building from:
echo   %NUVIO_DIR%
echo.
call "%~dp0BUILD_NUVIO.bat" "%NUVIO_DIR%"
if errorlevel 1 (
  echo.
  echo Build failed. The wrapper will NOT start an unbuilt Nuvio app.
  echo See build-nuvio.log for details.
  echo.
  pause
  exit /b 1
)

:READY
echo Using Nuvio:
echo   %NUVIO_DIR%\dist\index.html
echo.
echo Account/QR diagnostics: http://127.0.0.1:8797/__wrapper__/diagnostics
if not exist "%~dp0nuvio-wrapper.properties" echo QR/tracking config not set. Run CONFIGURE_NUVIO.bat when needed.

echo Checking for an older wrapper server on port 8797...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=(Get-NetTCPConnection -LocalPort 8797 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique); if($p){foreach($id in $p){try{Stop-Process -Id $id -Force -ErrorAction Stop}catch{}}}"

where py >nul 2>nul
if not errorlevel 1 goto :START_PY
where python >nul 2>nul
if not errorlevel 1 goto :START_PYTHON

echo ERROR: Python 3 is not installed or is not on PATH.
pause
exit /b 1

:START_PY
start "Nuvio Wrapper Server" cmd /k "cd /d ""%~dp0"" && py -3 ""%~dp0server.py"" --nuvio-root ""%NUVIO_DIR%"""
goto :OPEN

:START_PYTHON
start "Nuvio Wrapper Server" cmd /k "cd /d ""%~dp0"" && python ""%~dp0server.py"" --nuvio-root ""%NUVIO_DIR%"""
goto :OPEN

:OPEN
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:8797/"
exit /b 0
