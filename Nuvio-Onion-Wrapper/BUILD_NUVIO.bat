@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "LOG=%~dp0build-nuvio.log"

set "NUVIO_DIR=%~1"
if not defined NUVIO_DIR if defined NUVIO_PATH set "NUVIO_DIR=%NUVIO_PATH%"
if not defined NUVIO_DIR set "NUVIO_DIR=%~dp0nuvio"
for %%I in ("%NUVIO_DIR%") do set "NUVIO_DIR=%%~fI"

if not exist "%NUVIO_DIR%\package.json" (
  echo ERROR: Could not find Nuvio at "%NUVIO_DIR%".
  exit /b 1
)

>"%LOG%" echo ============================================================
>>"%LOG%" echo Nuvio Onion Wrapper - Nuvio Build
>>"%LOG%" echo Started %date% %time%
>>"%LOG%" echo Nuvio root: %NUVIO_DIR%
>>"%LOG%" echo ============================================================

where node >nul 2>nul || goto :NO_NODE
where npm >nul 2>nul || goto :NO_NPM

for /f "delims=" %%A in ('node --version') do set "NODEVER=%%A"
for /f "delims=" %%A in ('npm --version') do set "NPMVER=%%A"
echo Node: %NODEVER%
echo npm:  %NPMVER%
>>"%LOG%" echo Node: %NODEVER%
>>"%LOG%" echo npm: %NPMVER%

echo.
echo Installing Nuvio dependencies with npm install...
>>"%LOG%" echo [npm install]
pushd "%NUVIO_DIR%"
call npm install --no-audit --no-fund >>"%LOG%" 2>&1
set "RC=%ERRORLEVEL%"
popd
if not "%RC%"=="0" goto :NPM_FAIL

echo.
echo Building Nuvio browser app...
>>"%LOG%" echo [npm run build]
pushd "%NUVIO_DIR%"
call npm run build >>"%LOG%" 2>&1
set "RC=%ERRORLEVEL%"
popd
if not "%RC%"=="0" goto :BUILD_FAIL

if not exist "%NUVIO_DIR%\dist\index.html" goto :OUTPUT_FAIL
if not exist "%NUVIO_DIR%\dist\app.bundle.js" goto :OUTPUT_FAIL
if not exist "%NUVIO_DIR%\dist\core-js.bundle.js" goto :OUTPUT_FAIL
if not exist "%NUVIO_DIR%\dist\nuvio.env.js" goto :OUTPUT_FAIL

>>"%LOG%" echo BUILD SUCCESS %date% %time%
echo.
echo ============================================================
echo BUILD COMPLETE
echo ============================================================
echo Nuvio root: %NUVIO_DIR%
echo Inner app: %NUVIO_DIR%\dist\index.html
echo Build log: %LOG%
echo.
exit /b 0

:NO_NODE
echo ERROR: Node.js is not installed or not on PATH.
echo Install Node.js, open a NEW Command Prompt, then run this file again.
exit /b 1
:NO_NPM
echo ERROR: npm is not available on PATH.
exit /b 1
:NPM_FAIL
echo ERROR: npm install failed. See "%LOG%".
exit /b 1
:BUILD_FAIL
echo ERROR: npm run build failed. See "%LOG%".
exit /b 1
:OUTPUT_FAIL
echo ERROR: npm reported success, but the expected dist files are missing.
echo See "%LOG%".
exit /b 1
