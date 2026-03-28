@echo off
setlocal enabledelayedexpansion
title PDF OCR Tool

rem Configuration
set "SCRIPT_DIR=%~dp0"
set "ENVFILE=%SCRIPT_DIR%.env"
set "LASTPDF=%SCRIPT_DIR%last_pdf.txt"
set "PYTHON=python"

rem If a PDF path is passed (drag-drop or command line), run directly without menu
if not "%~1"=="" (
    set "PDFIN=%~1"
    call :normalize_path PDFIN PDFPATH
    if exist "!PDFPATH!" (
        call :start_ocr
        goto :eof
    ) else (
        echo File not found: "%~1"
        pause
        goto :menu
    )
)

:menu
cls
echo ========================================
echo       PDF OCR - NVIDIA NIM
echo ========================================
echo.
echo 1) Set/Update NVIDIA API key
echo 2) Run OCR on a PDF
echo 3) Rerun last PDF
echo 4) Test OCR (quick sanity check)
echo 5) Exit
echo.
choice /c 12345 /n /m "Select option: "
if errorlevel 5 goto :eof
if errorlevel 4 goto :test
if errorlevel 3 goto :rerun
if errorlevel 2 goto :run
if errorlevel 1 goto :setkey
goto :menu

:setkey
cls
echo Set NVIDIA API Key
echo -------------------------
set /p "NEWKEY=Enter your NVIDIA API key (nvapi-...): "
if "!NEWKEY!"=="" (
    echo No key entered.
    pause
    goto :menu
)
rem Save to .env (overwrite)
> "%ENVFILE%" echo NVIDIA_API_KEY=!NEWKEY!
echo.
echo API key saved to %ENVFILE%
echo.
pause
goto :menu

:run
cls
echo Run OCR on a PDF
echo -------------------------
echo You can type the full path (with spaces ok) or drag a file onto this window and paste.
set /p "PDFIN=Enter PDF path: "
if "!PDFIN!"=="" (
    echo No file specified.
    pause
    goto :menu
)
call :normalize_path PDFIN PDFPATH
if not exist "!PDFPATH!" (
    echo File not found: "!PDFPATH!"
    pause
    goto :menu
)
rem Save this as last PDF (raw, non‑quoted)
> "%LASTPDF%" echo(!PDFPATH!
goto :start_ocr

:rerun
cls
echo Rerun last PDF
echo -------------------------
if not exist "%LASTPDF%" (
    echo No previous PDF recorded.
    pause
    goto :menu
)
set /p "PDFIN="<"%LASTPDF%"
call :normalize_path PDFIN PDFPATH
if not exist "!PDFPATH!" (
    echo Last PDF no longer exists: "!PDFPATH!"
    del "%LASTPDF%"
    pause
    goto :menu
)
echo Using: "!PDFPATH!"
goto :start_ocr

:normalize_path
rem %1 = input variable name, %2 = output variable name
rem Strips outer quotes if present; also collapses double quotes inside.
set "in_val=!%~1!"
rem Remove surrounding quotes
if "!in_val:~0,1!"=="\"" if "!in_val:~-1!"=="\"" (
    set "in_val=!in_val:~1,-1!"
)
rem Also replace any remaining " with nothing (safety)
set "in_val=!in_val:"=!"
set "%~2=!in_val!"
goto :eof

:start_ocr
cls
echo Starting OCR...
echo.

rem Ensure Python is available
%PYTHON% --version >nul 2>&1
if errorlevel 1 (
    echo Python not found in PATH. Install Python 3.
    pause
    goto :menu
)

rem Ensure PyMuPDF (fitz); install if missing
%PYTHON% -c "import fitz" 2>nul
if errorlevel 1 (
    echo PyMuPDF is required. Installing now...
    pip install pymupdf
    if errorlevel 1 (
        echo.
        echo Installation failed. Install manually: pip install pymupdf
        pause
        goto :menu
    )
)

rem Load .env if present (in case batch is called outside menu)
if exist "%ENVFILE%" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%ENVFILE%") do (
        set "%%A=%%B"
    )
)

rem Run the Python driver with the clean path
%PYTHON% "%SCRIPT_DIR%ocr.py" "!PDFPATH!"
set "OCR_EXIT=%ERRORLEVEL%"

echo.
if %OCR_EXIT% neq 0 (
    echo OCR failed with exit code %OCR_EXIT%.
) else (
    echo OCR completed successfully.
    echo Output: %SCRIPT_DIR%full_output.txt
)
echo.
choice /c RN /n /m "Return to menu (R) or exit (N)? "
if errorlevel 2 exit /b %OCR_EXIT%
goto :menu

:test
cls
echo Test mode: verifying analyzer and API key
echo -------------------------
rem Ensure .env loaded
if exist "%ENVFILE%" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%ENVFILE%") do (
        set "%%A=%%B"
    )
)
rem Run test
%PYTHON% "%SCRIPT_DIR%ocr.py" --test
set "TEST_EXIT=%ERRORLEVEL%"
echo.
if %TEST_EXIT% neq 0 (
    echo Test FAILED.
) else (
    echo Test PASSED.
)
echo.
pause
goto :menu
