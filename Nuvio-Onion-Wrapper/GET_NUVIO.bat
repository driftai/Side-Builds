@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Usage:
rem   GET_NUVIO.bat                       -> installs/repairs Nuvio in .\nuvio
rem   GET_NUVIO.bat "D:\Apps\Nuvio"     -> installs/repairs a custom external location
rem   set NUVIO_PATH=D:\Apps\Nuvio      -> same custom-location support

set "TARGET=%~1"
if not defined TARGET if defined NUVIO_PATH set "TARGET=%NUVIO_PATH%"
if not defined TARGET set "TARGET=%~dp0nuvio"
for %%I in ("%TARGET%") do set "TARGET=%%~fI"

rem A directory by itself is NOT considered a valid Nuvio installation.
rem Require a small set of upstream files that prove the source tree is actually present.
set "MISSING=0"
if not exist "%TARGET%\package.json" set "MISSING=1"
if not exist "%TARGET%\appinfo.json" set "MISSING=1"
if not exist "%TARGET%\index.html" set "MISSING=1"
if not exist "%TARGET%\js\app.js" set "MISSING=1"

if "%MISSING%"=="0" (
  echo Nuvio installation is present and complete enough to use:
  echo   %TARGET%
  echo.
  echo The wrapper can use this location directly.
  echo.
  pause
  exit /b 0
)

if exist "%TARGET%\package.json" (
  echo Nuvio installation at "%TARGET%" is incomplete.
  echo Repairing it from the upstream repository...
) else if exist "%TARGET%" (
  echo Nuvio folder exists but does not contain a complete Nuvio installation.
  echo Installing Nuvio into:
  echo   %TARGET%
) else (
  echo Installing Nuvio into:
  echo   %TARGET%
)

echo.
set "ZIP=%TEMP%\nuvio-main.zip"
set "UNPACK=%TEMP%\nuvio-unpack"
set "URL=https://github.com/NuvioMedia/NuvioTVSmart/archive/refs/heads/main.zip"

echo Downloading NuvioTVSmart...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -Uri '%URL%' -OutFile '%ZIP%' -UseBasicParsing; exit 0 } catch { Write-Host $_; exit 1 }"
if errorlevel 1 goto :FAIL
if exist "%UNPACK%" rmdir /s /q "%UNPACK%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%ZIP%' -DestinationPath '%UNPACK%' -Force"
if errorlevel 1 goto :FAIL
set "SRC="
for /d %%D in ("%UNPACK%\NuvioTVSmart-*") do set "SRC=%%D"
if not defined SRC goto :FAIL
if not exist "%TARGET%" mkdir "%TARGET%"
robocopy "%SRC%" "%TARGET%" /E /NFL /NDL /NJH /NJS >nul
if errorlevel 8 goto :FAIL

rem Verify the install was repaired, not just copied into an existing folder.
if not exist "%TARGET%\package.json" goto :VERIFY_FAIL
if not exist "%TARGET%\appinfo.json" goto :VERIFY_FAIL
if not exist "%TARGET%\index.html" goto :VERIFY_FAIL
if not exist "%TARGET%\js\app.js" goto :VERIFY_FAIL

del /q "%ZIP%" >nul 2>nul
rmdir /s /q "%UNPACK%" >nul 2>nul
echo.
echo Nuvio installation is ready at:
echo   %TARGET%
echo.
echo The Nuvio source is user-local and is not part of the wrapper repository.
echo Run START_WRAPPER.bat or START_WRAPPER.bat "%TARGET%" next.
echo.
pause
exit /b 0

:VERIFY_FAIL
echo.
echo Nuvio was downloaded, but the required source files are still missing.
echo Target:

echo   %TARGET%
echo.
goto :FAIL_CLEAN

:FAIL
echo.
echo Nuvio download/install failed.

:FAIL_CLEAN
del /q "%ZIP%" >nul 2>nul
rmdir /s /q "%UNPACK%" >nul 2>nul
pause
exit /b 1
