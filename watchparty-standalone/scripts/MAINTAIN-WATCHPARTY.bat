@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
set "ROOT=%~dp0.."
set "SCRIPTS=%~dp0"

echo =====================================================
echo          WATCHPARTY PROJECT ORGANIZER
echo =====================================================
echo.
echo This will:
echo  - move any known startup .bat files from the root into scripts\
echo  - remove obsolete patch/remote documentation files
echo  - remove stray WatchParty patch ZIPs from the project root
echo  - keep the main application, public\, tools\ and README files intact
echo.

for %%F in (ALLOW-LAN-FIREWALL.bat START-WATCHPARTY-LAN.bat START-WATCHPARTY-LOCAL.bat START-WATCHPARTY-REMOTE.bat STOP-WATCHPARTY-REMOTE.bat CLEANUP-WATCHPARTY-BLOAT.bat) do (
  if exist "%ROOT%\%%F" (
    move /Y "%ROOT%\%%F" "%SCRIPTS%%%F" >nul
    echo Moved %%F to scripts\
  )
)

if exist "%ROOT%\MODULARIZE-WATCHPARTY.bat" (
  del /Q "%ROOT%\MODULARIZE-WATCHPARTY.bat"
  echo Removed obsolete MODULARIZE-WATCHPARTY.bat
)

for %%F in (README-CLEANUP.txt README-MODULAR.txt README-PATCH.txt README-REMOTE-UPDATE.txt README-REMOTE.md) do (
  if exist "%ROOT%\%%F" (
    del /Q "%ROOT%\%%F"
    echo Removed obsolete %%F
  )
)

for %%F in (WatchParty-Standalone-*.zip *.zip) do (
  if exist "%ROOT%\%%F" (
    del /Q "%ROOT%\%%F"
    echo Removed stray project ZIP: %%F
  )
)

if not exist "%ROOT%\scripts" mkdir "%ROOT%\scripts" >nul 2>&1
if not exist "%ROOT%\tools" mkdir "%ROOT%\tools" >nul 2>&1

echo.
echo Project organization complete.
echo.
echo Root startup: WatchParty.bat
echo Operational scripts: scripts\
echo Cloudflared binary: tools\cloudflared.exe
echo.
pause
endlocal
