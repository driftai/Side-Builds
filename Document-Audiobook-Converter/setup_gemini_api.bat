@echo off
echo ===========================================
echo    Gemini API Setup Helper
echo ===========================================
echo.

REM Check if API key is already set
if not "%GEMINI_API_KEY%"=="" (
    echo Current API key is set (ends with: ...%GEMINI_API_KEY:~-4%)
    echo.
    set /p choice="Do you want to update it? (y/n): "
    if /i not "%choice%"=="y" goto END
)

echo Please enter your Gemini API key from Google AI Studio:
echo https://makersuite.google.com/app/apikey
echo.
echo Note: Your API key should start with "AIza"
echo.

set /p api_key="Enter your Gemini API key: "

REM Basic validation
if "%api_key%"=="" (
    echo ERROR: API key cannot be empty
    pause
    exit /b 1
)

if not "%api_key:~0,4%"=="AIza" (
    echo WARNING: API key should start with "AIza"
    echo This may not be a valid Gemini API key
    set /p confirm="Continue anyway? (y/n): "
    if /i not "%confirm%"=="y" (
        echo Setup cancelled
        pause
        exit /b 1
    )
)

REM Set the environment variable
setx GEMINI_API_KEY "%api_key%" /M
set GEMINI_API_KEY=%api_key%

echo.
echo ✅ Gemini API key has been set!
echo The key will persist across system restarts.
echo.
echo Current key: %api_key:~0,8%...%api_key:~-4%
echo.
echo You can now run the servers with:
echo   start_with_gemini_live.bat
echo.

:END
echo Press any key to exit...
pause >nul
