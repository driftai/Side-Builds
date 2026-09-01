@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

set "ROOT=%CD%"
set "RUNTIME=%ROOT%\.runtime"

if not exist "%RUNTIME%" mkdir "%RUNTIME%" >nul 2>&1

REM ------------------------------------------------------------
REM Rebuild Local/LAN state from the actual 9085 listener.
REM ------------------------------------------------------------

del /q "%RUNTIME%\local.active" >nul 2>&1
del /q "%RUNTIME%\lan.active" >nul 2>&1

powershell.exe -NoProfile -Command ^
    "$tcp=Get-NetTCPConnection -LocalPort 9085 -State Listen -ErrorAction SilentlyContinue;" ^
    "if($tcp) {" ^
    "  $addresses=@($tcp | Select-Object -ExpandProperty LocalAddress -Unique);" ^
    "  if($addresses -contains '0.0.0.0' -or $addresses -contains '::') {" ^
    "    'LAN' | Set-Content -Encoding ASCII '%RUNTIME%\lan.active';" ^
    "  } elseif($addresses -contains '127.0.0.1' -or $addresses -contains '::1') {" ^
    "    'LOCAL' | Set-Content -Encoding ASCII '%RUNTIME%\local.active';" ^
    "  }" ^
    "}"

endlocal
exit /b 0
