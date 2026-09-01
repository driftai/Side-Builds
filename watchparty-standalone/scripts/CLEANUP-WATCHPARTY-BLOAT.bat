@echo off
setlocal
cd /d "%~dp0"
set "removed=0"
echo Cleaning obsolete WatchParty helper files...
echo.
for %%F in (
  "CLEANUP-OLD-NAMED-CLOUDFLARE-SERVICE.bat"
  "CLOUDFLARE-ACCESS-NEXT.txt"
  "INSTALL-CLOUDFLARED.bat"
  "SETUP-CLOUDFLARE-REMOTE.bat"
  "START-WATCHPARTY.bat"
  "START-WATCHPARTY.ps1"
  "README-PATCH.txt"
  "README-REMOTE-UPDATE.txt"
  "README-REMOTE.md"
) do (
  if exist "%%~F" (
    del /q "%%~F"
    if not exist "%%~F" (
      echo Removed %%~F
      set /a removed+=1
    ) else (
      echo Could not remove %%~F
    )
  )
)
echo.
echo Cleanup complete. Removed %removed% obsolete files.
echo.
echo Retained core files:
echo   server.js / package.json
 echo   public\
 echo   tools\cloudflared.exe
 echo   START-WATCHPARTY-LOCAL.bat
 echo   START-WATCHPARTY-LAN.bat
 echo   START-WATCHPARTY-REMOTE.bat
 echo   STOP-WATCHPARTY-REMOTE.bat
 echo  echo   ALLOW-LAN-FIREWALL.bat
 echo   README.md / UPSTREAM-NOTICE.md
 echo.
pause
endlocal
