@echo off
echo ===========================================
echo    Audiobook Converter with Gemini Live API
echo ===========================================
echo.

REM Change to the project directory
cd /d "%~dp0"

REM Check for required files
if not exist "package.json" (
    echo ERROR: package.json not found in current directory
    echo Current directory: %CD%
    echo Please run this script from the project root directory
    pause
    exit /b 1
)

REM Check if GeminiEngine server is accessible
if not exist "backend\main.py" (
    echo ERROR: GeminiEngine server not found at backend
    echo Please ensure the GeminiEngine server is installed
    pause
    exit /b 1
)

REM Python check removed - GeminiEngine server handles Python requirements

REM Check for Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js is not installed or not in PATH
    echo Please install Node.js v18+ from https://nodejs.org/
    pause
    exit /b 1
)

REM Check for GEMINI_API_KEY environment variable
if "%GEMINI_API_KEY%"=="" (
    echo WARNING: GEMINI_API_KEY environment variable not set
    echo Please set it with: set GEMINI_API_KEY=your_api_key_here
    echo The server will still start but Gemini features won't work
    echo.
)

REM Auto-install dependencies if missing
if not exist "node_modules" (
    echo INFO: node_modules not found - installing Node.js dependencies...
    echo.
    call npm install
    if errorlevel 1 (
        echo ERROR: Failed to install Node.js dependencies
        pause
        exit /b 1
    )
    echo.
)

REM Python dependencies removed - using centralized GeminiEngine server

echo Starting servers...
echo.

REM Start GeminiEngine WebSocket server in background
echo Starting GeminiEngine WebSocket Server (port 9083)...
cd /d "backend"
start /B python main.py
cd /d "%~dp0"
timeout /t 3 /nobreak >nul

REM Start React development server
echo Starting React Development Server (port 5173)...
start /B npm run dev
timeout /t 3 /nobreak >nul

REM Wait for servers to start
echo Waiting for servers to initialize...
timeout /t 5 /nobreak >nul

echo.
echo ===========================================
echo    Servers Started Successfully!
echo ===========================================
echo.
echo 🌐 React App:       http://localhost:5173
echo 🔗 WebSocket:       ws://localhost:9083 (GeminiEngine)
echo 📊 Status API:      http://localhost:9084/status
echo.
echo Using centralized GeminiEngine server for all WebSocket connections.
echo.
echo To stop the servers:
echo 1. Close this command window
echo 2. The servers will stop automatically
echo.
echo Press any key to exit this launcher...
pause >nul
