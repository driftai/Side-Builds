@echo off
setlocal enabledelayedexpansion

:: Set the working directory to the script's location
cd /d "%~dp0"

set "SERVER_PORT=5173"
set "SERVER_URL=http://localhost:%SERVER_PORT%"
set "SERVER_WINDOW_TITLE=Vite Dev Server"

:MainMenu
cls
echo ================================
echo Vite Server Management
echo ================================
echo.
call :CheckServerStatus
echo.
echo Options:
echo [1] Start Server
echo [2] Open Site in Browser
echo [3] Start Server ^& Open Site
echo [4] Stop Server
echo [5] Exit
echo.
set /p choice="Enter your choice (1-5): "

if "%choice%"=="1" (
    call :StopSpecificServer
    call :StartDevServer
    goto :MainMenu
)
if "%choice%"=="2" (
    call :OpenSite
    goto :MainMenu
)
if "%choice%"=="3" (
    call :StopSpecificServer
    call :StartDevServer
    timeout /t 3 /nobreak >nul
    call :OpenSite
    goto :MainMenu
)
if "%choice%"=="4" (
    call :StopSpecificServer
    goto :MainMenu
)
if "%choice%"=="5" (
    exit /b
)
echo Invalid choice. Please try again.
timeout /t 2 /nobreak >nul
goto :MainMenu

:StartDevServer
echo Starting Vite development server...
:: Start npm run dev in a new minimized window with a specific title
start "%SERVER_WINDOW_TITLE%" /min cmd /k "npm run dev"
echo Server starting in a new window. Please wait a few moments for it to initialize.
timeout /t 5 /nobreak >nul
goto :eof

:OpenSite
echo Opening %SERVER_URL% in your default browser...
start "" "%SERVER_URL%"
goto :eof

:StopSpecificServer
echo Stopping server on port %SERVER_PORT%...

:: First, close any existing Vite Dev Server windows
echo Closing existing server windows...
taskkill /F /FI "WINDOWTITLE eq %SERVER_WINDOW_TITLE%*" 2>nul
taskkill /F /FI "WINDOWTITLE eq Select %SERVER_WINDOW_TITLE%*" 2>nul

set "max_attempts=5"
set "attempt=0"

:KillLoop
set /a attempt+=1
if %attempt% GTR %max_attempts% (
    echo ERROR: Could not free port %SERVER_PORT% after %max_attempts% attempts.
    echo Please close any applications using port %SERVER_PORT% or run as Administrator.
    goto :eof
)

:: Check if port is in use
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%SERVER_PORT%.*LISTENING" 2^>nul') do (
    echo Attempt %attempt%: Found PID %%a on port %SERVER_PORT%. Killing...
    taskkill /F /PID %%a /T >nul 2>&1
    powershell -Command "Stop-Process -Id %%a -Force -ErrorAction SilentlyContinue" 2>nul
)

:: Brief pause to let the OS release the port
timeout /t 2 /nobreak >nul

:: Check if still in use
netstat -ano | findstr ":%SERVER_PORT%.*LISTENING" >nul 2>&1
if %ERRORLEVEL%==0 (
    echo Port still in use, retrying...
    goto :KillLoop
)

echo Port %SERVER_PORT% is now free.
goto :eof

:CheckServerStatus
set "isRunning=0"
netstat -ano | findstr ":%SERVER_PORT%.*LISTENING" >nul
if %ERRORLEVEL%==0 (
    set "isRunning=1"
)

if "!isRunning!"=="1" (
    echo Server Status: RUNNING on %SERVER_URL%
) else (
    echo Server Status: STOPPED
)
goto :eof

endlocal 