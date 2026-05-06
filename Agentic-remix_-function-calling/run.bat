@echo off
title Smart Home Light Controller
color 0A
chcp 65001 >nul 2>&1

:menu
cls
echo.
echo   +--------------------------------------+
echo   ^|   Smart Home Light Controller        ^|
echo   +--------------------------------------+
echo   ^|  [1] Start dev server                ^|
echo   ^|  [2] Stop dev server                 ^|
echo   ^|  [3] Open in browser                 ^|
echo   ^|  [4] Exit                            ^|
echo   +--------------------------------------+
echo.
set /p choice="  Select: "

if "%choice%"=="1" goto start
if "%choice%"=="2" goto stop
if "%choice%"=="3" goto open
if "%choice%"=="4" exit /b

echo  Invalid choice.
timeout /t 2 >nul
goto menu

:start
echo.
echo  Starting dev server...
cd /d "%~dp0"
start "LightController-Dev" cmd /c "npm run dev"
echo  Server started. Access at http://localhost:3000/
timeout /t 3 >nul
goto menu

:stop
echo.
echo  Stopping dev server...
taskkill /FI "WINDOWTITLE eq LightController-Dev*" /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000" ^| findstr "LISTENING" 2^>nul') do (
    taskkill /PID %%a /F >nul 2>&1
)
echo  Server stopped.
timeout /t 2 >nul
goto menu

:open
start http://localhost:3000/
goto menu
