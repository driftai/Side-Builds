@echo off
echo ===========================================
echo    Simple Audiobook Converter Launcher
echo    (Updated: Enhanced timing for slower playback)
echo ===========================================
echo.

REM Change to the audiobook converter directory
cd /d "%~dp0"

REM Quick check for required files (optional - shows info but doesn't block)
if not exist "package.json" (
    echo WARNING: package.json not found in current directory
    echo Current directory: %CD%
    echo This might indicate the batch file is in the wrong location
    echo Continuing anyway...
    echo.
)

REM Quick check for Node.js (optional - shows info but doesn't block)
node --version >nul 2>&1
if errorlevel 1 (
    echo WARNING: Node.js might not be installed or not in PATH
    echo If the server fails to start, install Node.js from https://nodejs.org/
    echo Required: Node.js v18+ (v20+ recommended)
    echo Continuing anyway...
    echo.
)

REM Auto-install dependencies if missing (but don't block if it fails)
if not exist "node_modules" (
    echo INFO: node_modules not found - attempting to install dependencies...
    echo.
    call npm install
    echo.
)

echo Starting audiobook converter with enhanced timing and speed control...
echo Features: 1.5-second delays between sentences, normal generation speed, 0.4x playback rate
echo.
echo Launching servers... (this may take a moment)
echo.

REM Start the React dev server
echo Starting React development server...
start /B npm run dev

echo Waiting for React server to start... (manual Electron launch is now required)
timeout /t 5 /nobreak >nul

:CHOICE_MENU
echo.
echo ===========================================
echo    Audiobook Converter Started!
echo ===========================================
echo.
echo React Dev Server: Check console output above (typically http://localhost:5173 or http://localhost:5174 if 5173 is in use)
echo.
echo What would you like to do?
echo 1. Launch Electron Floating Controls (Recommended for full features)
echo 2. Exit Launcher (React server will keep running in background)
echo.
set /p CHOICE="Enter your choice (1 or 2): "

if /i "%CHOICE%"=="1" goto LAUNCH_ELECTRON
if /i "%CHOICE%"=="2" goto EXIT_LAUNCHER
echo Invalid choice. Please enter 1 or 2.
goto CHOICE_MENU

:LAUNCH_ELECTRON
echo Launching Electron Floating Controls...
start /B npm run electron
goto END_SCRIPT

:EXIT_LAUNCHER
echo Exiting launcher. React server will continue running in the background.
goto END_SCRIPT

:END_SCRIPT

REM To stop: Close this window and kill processes manually

echo.
echo ===========================================
echo    Audiobook Converter Server Stopped
echo ===========================================

echo.
echo If you need to restart, run this batch file again.
echo Press any key to exit...
pause
