@echo off
setlocal
cd /d "%~dp0"
echo.
echo Piano Auto Player - YouTube to Piano one-time setup / repair
echo ============================================================
echo.

py -3.10 -c "import sys; print(sys.version)" >nul 2>&1
if errorlevel 1 (
  echo Python 3.10 was not found. Basic Pitch 0.4.0 supports Python 3.10 and 3.11,
  echo but this project keeps its lightweight Windows ONNX path on Python 3.10.
  where winget >nul 2>&1
  if errorlevel 1 (
    echo Install Python 3.10, then run this file again.
    pause
    exit /b 1
  )
  echo Installing Python 3.10 with winget...
  winget install -e --id Python.Python.3.10 --accept-package-agreements --accept-source-agreements
  if errorlevel 1 goto :failed
)

if not exist ".youtube-piano-venv\Scripts\python.exe" (
  echo Creating isolated transcription environment...
  py -3.10 -m venv .youtube-piano-venv
  if errorlevel 1 goto :failed
)

echo Updating Basic Pitch, yt-dlp, PO-token helper, and alternate-source search...
".youtube-piano-venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :failed
rem yt-dlp recommends its nightly/pre-release track when the current stable has a YouTube issue.
rem [default] installs the matching yt-dlp-ejs version automatically.
".youtube-piano-venv\Scripts\python.exe" -m pip install --upgrade --pre "yt-dlp[default]" basic-pitch yt-dlp-getpot-wpc ddgs
if errorlevel 1 goto :failed

rem Deno is yt-dlp's preferred JS runtime. Install it even when an arbitrary Node
rem happens to exist so an old Node version cannot make setup look ready.
where deno >nul 2>&1
if errorlevel 1 (
  where winget >nul 2>&1
  if not errorlevel 1 (
    echo Installing Deno, yt-dlp's preferred YouTube JavaScript runtime...
    winget install -e --id DenoLand.Deno --accept-package-agreements --accept-source-agreements
    if errorlevel 1 goto :node_fallback
    goto :runtime_ready
  )
  goto :node_fallback
) else (
  where winget >nul 2>&1
  if not errorlevel 1 winget upgrade -e --id DenoLand.Deno --accept-package-agreements --accept-source-agreements >nul 2>&1
  goto :runtime_ready
)

:node_fallback
where node >nul 2>&1
if errorlevel 1 (
  echo Deno 2.3+ or Node 22+ is required for YouTube challenge solving.
  echo Install Deno, then run this file again.
  pause
  exit /b 1
)
for /f %%V in ('node -p "process.versions.node.split('.')[0]" 2^>nul') do set NODE_MAJOR=%%V
if not defined NODE_MAJOR goto :runtime_failed
if %NODE_MAJOR% LSS 22 goto :runtime_failed
echo Deno could not be installed, but Node %NODE_MAJOR%+ is available as a supported fallback.
goto :runtime_ready

:runtime_failed
echo The installed Node.js is too old. yt-dlp requires Node 22+.
echo Install Deno 2.3+ or upgrade Node, then run this file again.
pause
exit /b 1

:runtime_ready
where ffmpeg >nul 2>&1
if errorlevel 1 (
  where winget >nul 2>&1
  if errorlevel 1 (
    echo FFmpeg was not found. Install FFmpeg and make sure ffmpeg.exe and ffprobe.exe are on PATH.
    pause
    exit /b 1
  )
  echo Installing FFmpeg with winget...
  winget install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
  if errorlevel 1 goto :failed
)

echo.
echo Setup repair complete.
echo Restart start.bat so newly installed Deno/PATH changes are visible.
echo The media card will show the exact JS runtime, PO-token helper, and alternate search it detected.
echo Automatic mode no longer reads browser cookie databases; browser sessions are opt-in only.
pause
exit /b 0

:failed
echo.
echo Setup did not finish successfully. Review the error above, then run this file again.
pause
exit /b 1
