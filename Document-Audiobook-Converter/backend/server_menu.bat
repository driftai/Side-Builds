@echo off
setlocal enabledelayedexpansion

:: Set the working directory to the script's location
cd /d "%~dp0"

:: Script can be run from any directory

:: Handle stop command from external calls
if "%1"=="stop" (
    call :StopAllServers
    exit /b
)

:: Ensure Python is in the PATH
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: Python not found in PATH. Please install Python and add it to your PATH.
    pause
    exit /b 1
)

:: Go directly to menu without starting servers
goto :MainMenu

:MainMenu
cls
echo ================================
echo Server Management Console
echo ================================
echo.
echo Current Status:
call :CheckServerStatus "Main Server" "9083"
echo.
echo Options:
echo [1] Start Main Server (9083)
echo [2] Stop Main Server (9083)
echo [3] Open WebSocket Server Interface
echo [4] Exit
echo.
set /p choice="Enter your choice (1-4): "

if "%choice%"=="1" (
    call :StopServer "Main Server" "9083"
    timeout /t 2 /nobreak >nul
    call :StartServer "Main Server" "main.py" "9083"
    goto :MainMenu
)
if "%choice%"=="2" (
    call :StopServer "Main Server" "9083"
    goto :MainMenu
)
if "%choice%"=="3" (
    echo Opening WebSocket Server Interface...
    start http://localhost:9083
    goto :MainMenu
)
if "%choice%"=="4" (
    exit /b
)
goto :MainMenu


:StartServer
set "server_type=%~1"
set "script_name=%~2"
set "port_number=%~3"
echo Starting %server_type%...

:: Validate server type and port combination
if "%server_type%"=="Main Server" if not "%port_number%"=="9083" (
    echo ERROR: Main Server must use port 9083
    goto :eof
)

:: Enhanced process cleanup for Main Server
if "%server_type%"=="Main Server" (
    echo Performing thorough cleanup for Main Server...

    :: Kill by window title
    taskkill /F /FI "WINDOWTITLE eq Main Server*" /T >nul 2>&1
    taskkill /F /FI "WINDOWTITLE eq *main.py*" /T >nul 2>&1

    :: Kill by port
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":9083.*LISTENING"') do (
        taskkill /F /PID %%a >nul 2>&1
    )

    :: Kill any python processes that might be running main.py
    for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq python.exe" /v ^| findstr /i "main.py"') do (
        taskkill /F /PID %%a >nul 2>&1
    )

    :: Remove any temporary files
    if exist "run_main_temp.bat" del /F "run_main_temp.bat" >nul 2>&1

    :: Wait for processes to be fully killed
    timeout /t 3 /nobreak >nul
)

:: Check if script exists
if not exist "%script_name%" (
    echo ERROR: %script_name% not found in current directory
    echo Current directory: %CD%
    dir
    goto :eof
)

:: Start the server based on type
if "%server_type%"=="Main Server" (
    echo Starting Main Server...
    :: Set the Google API key and start the server in a minimized window
    :: The key comes from your environment or .env.local - never hardcode it here.
    start "Main Server Port 9083" /min cmd /c "cd /d "%~dp0" && python -u main.py 2>&1"
)

:: Give it time to start
timeout /t 3 /nobreak >nul

:: Check if server started (try multiple times)
set "server_started=0"
for /l %%i in (1,1,3) do (
    netstat -ano | findstr ":%port_number%.*LISTENING" >nul
    if !ERRORLEVEL!==0 (
        set "server_started=1"
        echo %server_type% started successfully on port %port_number%
        if "%server_type%"=="Main Server" (
            if exist "run_main_temp.bat" del /F "run_main_temp.bat" >nul 2>&1
        )
        goto :eof
    )
    echo Checking server status... Attempt %%i of 3
    timeout /t 1 /nobreak >nul
)

if "!server_started!"=="0" (
    echo WARNING: %server_type% may have failed to start. Checking port %port_number%...
    netstat -ano | findstr ":%port_number%"
    if "%server_type%"=="Main Server" (
        echo Please check the Main Server window for error messages
        echo The window will stay open if there were any errors
    )
)

goto :eof

:StopAllServers
echo.
echo Stopping Main Server...
echo.

:: Stop Main Server
call :StopServer "Main Server" "9083"

:: Final cleanup
echo.
echo === Final Cleanup ===
taskkill /F /FI "IMAGENAME eq python.exe" /T >nul 2>&1
timeout /t 2 /nobreak >nul

echo.
echo === Final Status Check ===
call :CheckServerStatus "Main Server" "9083"
goto :eof

:StopServer
echo Stopping %~1...
:: Parameters: %1 = server name, %2 = port number

:: Kill processes for the specific server type
if "%~1"=="Main Server" (
    echo Stopping Main server processes...
    taskkill /F /FI "WINDOWTITLE eq *Main Server Port 9083*" /T >nul 2>&1
    taskkill /F /FI "WINDOWTITLE eq *main.py*" /T >nul 2>&1
    :: Also kill any Python process using port 9083
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":9083.*LISTENING"') do (
        echo Found Main server process on port 9083 (PID: %%a)
        taskkill /F /PID %%a /T >nul 2>&1
    )
)

:: Then kill any process using the port
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%~2.*LISTENING"') do (
    echo Found process on port %~2 with PID: %%a
    taskkill /F /PID %%a /T >nul 2>&1
)

:: Wait a bit and verify
timeout /t 2 /nobreak >nul

:: Final aggressive cleanup for this specific server
taskkill /F /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq *%~1*" /T >nul 2>&1

:: Check if the port is truly free
call :CheckServerStatus "%~1" "%~2" >nul
if %ERRORLEVEL%==0 (
    echo WARNING: Failed to stop %~1 on port %~2
    echo Attempting final force kill...
    :: One last attempt with maximum force
    taskkill /F /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq *%~1*" /T >nul 2>&1
    timeout /t 1 /nobreak >nul
)

:: Final status report
call :CheckServerStatus "%~1" "%~2"
goto :eof

:CheckServerStatus
:: Parameters: %1 = server name, %2 = port number
set "server_name=%~1"
set "port=%~2"

:: More thorough port check
set "is_running=0"

:: Check for LISTENING state specifically
netstat -ano | findstr /R ":%port%.*LISTENING" >nul
if %ERRORLEVEL%==0 set "is_running=1"

:: Also check for ESTABLISHED connections on that port
netstat -ano | findstr /R ":%port%.*ESTABLISHED" >nul
if %ERRORLEVEL%==0 set "is_running=1"

:: Report status
if "!is_running!"=="1" (
    echo %server_name%: RUNNING ^(Port %port%^)
    exit /b 0
) else (
    echo %server_name%: STOPPED ^(Port %port%^)
    exit /b 1
) 