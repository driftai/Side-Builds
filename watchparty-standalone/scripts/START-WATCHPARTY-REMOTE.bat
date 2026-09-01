@echo off
setlocal EnableExtensions
set "ROOT=%~dp0.."

for %%R in ("%ROOT%") do set "ROOT=%%~fR"

title WatchParty Standalone - Remote

rem Cloudflared is a user-installed dependency.
rem Place cloudflared.exe at: <WatchParty>\tools\cloudflared.exe
set "CLOUDFLARED=%ROOT%\tools\cloudflared.exe"

if not exist "%CLOUDFLARED%" (
    echo.
    echo ERROR: cloudflared.exe was not found.
    echo.
    echo WatchParty Remote mode requires Cloudflare cloudflared.
    echo Download it from the official Cloudflare downloads page:
    echo https://developers.cloudflare.com/tunnel/downloads/
    echo.
    echo Then place the Windows executable here:
    echo   %CLOUDFLARED%
    echo.
    echo Rename it to cloudflared.exe if necessary.
    echo.
    pause
    exit /b 1
)

echo.
echo Using Cloudflared:
echo   %CLOUDFLARED%
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass ^
    -File "%ROOT%\scripts\REMOTE-TUNNEL.ps1" ^
    -Root "%ROOT%" ^
    -Cloudflared "%CLOUDFLARED%"

set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
    echo.
    echo Remote startup exited with code %RC%.
    pause
)

endlocal
exit /b %RC%
