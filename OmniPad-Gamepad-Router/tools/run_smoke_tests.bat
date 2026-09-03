@echo off
setlocal
title OmniPad Smoke Tests
cd /d "%~dp0\.."

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Running setup...
    call tools\setup_env.bat
    if errorlevel 1 goto :setup_failed
)

if not exist ".venv\Scripts\python.exe" goto :setup_failed

echo Running OmniPad Architecture Check...
".\.venv\Scripts\python.exe" tools\check_architecture.py
if errorlevel 1 exit /b 1

echo Running OmniPad Security Boundary Tests...
".\.venv\Scripts\python.exe" tests\test_security.py
if errorlevel 1 exit /b 1

echo Running OmniPad Endpoint Access Control ^& Redaction Tests...
".\.venv\Scripts\python.exe" tests\test_security_boundaries.py
if errorlevel 1 exit /b 1

echo Running OmniPad WebSocket Authorization ^& Observer Containment Tests...
".\.venv\Scripts\python.exe" tests\test_websocket_security.py
if errorlevel 1 exit /b 1

echo Running OmniPad Target Discovery Tests...
".\.venv\Scripts\python.exe" tests\test_targeting.py
if errorlevel 1 exit /b 1

echo Running OmniPad Keyboard Bridge Tests...
".\.venv\Scripts\python.exe" tests\test_keyboard_bridge.py
if errorlevel 1 exit /b 1

echo Running OmniPad VHF Keyboard Report Tests...
".\.venv\Scripts\python.exe" tests\test_vhf_keyboard.py
if errorlevel 1 exit /b 1

echo Running OmniPad Raw Input Keyboard Enumeration Tests...
".\.venv\Scripts\python.exe" tests\test_raw_input_keyboards.py
if errorlevel 1 exit /b 1

echo Running OmniPad Backend Transitions ^& Failure Recovery Tests...
".\.venv\Scripts\python.exe" tests\test_backend_transitions.py
if errorlevel 1 exit /b 1

echo Running OmniPad Independent Surface-to-Output Routing Tests...
".\.venv\Scripts\python.exe" tests\test_surface_output_routing.py
if errorlevel 1 exit /b 1

echo Running OmniPad End-to-End Surface-to-Output Combinations Tests...
".\.venv\Scripts\python.exe" tests\test_surface_combinations_e2e.py
if errorlevel 1 exit /b 1

echo Running OmniPad WebSocket Join ^& Real-Time Input Streaming Tests...
".\.venv\Scripts\python.exe" tests\test_player_websocket_join.py
if errorlevel 1 exit /b 1

echo Running OmniPad Core Smoke Tests...
".\.venv\Scripts\python.exe" tests\smoke_test.py
if errorlevel 1 exit /b 1

pause
exit /b 0

:setup_failed
echo.
echo ERROR: OmniPad environment setup failed. Smoke tests were not started.
pause
exit /b 1
