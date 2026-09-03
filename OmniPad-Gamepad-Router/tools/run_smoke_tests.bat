@echo off
setlocal
title OmniPad Smoke Tests
cd /d "%~dp0\.."
set "PYTHON=.\.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo Virtual environment not found. Running setup...
    goto :run_setup
)

"%PYTHON%" -c "import fastapi, uvicorn, vgamepad" >nul 2>&1
if errorlevel 1 (
    echo OmniPad environment incomplete. Running setup...
    goto :run_setup
)
goto :run_tests

:run_setup
call tools\setup_env.bat
if errorlevel 1 goto :setup_failed
if not exist "%PYTHON%" goto :setup_failed
"%PYTHON%" -c "import fastapi, uvicorn, vgamepad" >nul 2>&1
if errorlevel 1 goto :setup_failed

:run_tests
echo Running OmniPad Architecture Check...
"%PYTHON%" tools\check_architecture.py
if errorlevel 1 exit /b 1

echo Running OmniPad Control Center Tests...
"%PYTHON%" tests\test_control_center.py
if errorlevel 1 exit /b 1

echo Running OmniPad Security Boundary Tests...
"%PYTHON%" tests\test_security.py
if errorlevel 1 exit /b 1

echo Running OmniPad Endpoint Access Control ^& Redaction Tests...
"%PYTHON%" tests\test_security_boundaries.py
if errorlevel 1 exit /b 1

echo Running OmniPad WebSocket Authorization ^& Observer Containment Tests...
"%PYTHON%" tests\test_websocket_security.py
if errorlevel 1 exit /b 1

echo Running OmniPad Target Discovery Tests...
"%PYTHON%" tests\test_targeting.py
if errorlevel 1 exit /b 1

echo Running OmniPad Keyboard Bridge Tests...
"%PYTHON%" tests\test_keyboard_bridge.py
if errorlevel 1 exit /b 1

echo Running OmniPad Background Keyboard Helper Tests...
"%PYTHON%" tests\test_background_keyboard_helper.py
if errorlevel 1 exit /b 1

echo Running OmniPad VHF Keyboard Report Tests...
"%PYTHON%" tests\test_vhf_keyboard.py
if errorlevel 1 exit /b 1

echo Running OmniPad Normal-Mode UMDF Virtual Keyboard Tests...
"%PYTHON%" tests\test_umdf_keyboard.py
if errorlevel 1 exit /b 1

echo Running OmniPad Raw Input Keyboard Enumeration Tests...
"%PYTHON%" tests\test_raw_input_keyboards.py
if errorlevel 1 exit /b 1

echo Running OmniPad Backend Transitions ^& Failure Recovery Tests...
"%PYTHON%" tests\test_backend_transitions.py
if errorlevel 1 exit /b 1

echo Running OmniPad Independent Surface-to-Output Routing Tests...
"%PYTHON%" tests\test_surface_output_routing.py
if errorlevel 1 exit /b 1

echo Running OmniPad End-to-End Surface-to-Output Combinations Tests...
"%PYTHON%" tests\test_surface_combinations_e2e.py
if errorlevel 1 exit /b 1

echo Running OmniPad Touchscreen Controller Tests...
"%PYTHON%" tests\test_touch_controller.py
if errorlevel 1 exit /b 1

echo Running OmniPad Touchscreen Layout Preset Tests...
"%PYTHON%" tests\test_touch_controller_layouts.py
if errorlevel 1 exit /b 1

echo Running OmniPad Remote Player Input Feature Tests...
"%PYTHON%" tests\test_remote_player_input_features.py
if errorlevel 1 exit /b 1

echo Running OmniPad WebSocket Join ^& Real-Time Input Streaming Tests...
"%PYTHON%" tests\test_player_websocket_join.py
if errorlevel 1 exit /b 1

echo Running OmniPad Live Server Integration Tests...
"%PYTHON%" tests\test_server_live.py
if errorlevel 1 exit /b 1

echo Running OmniPad Core Smoke Tests...
"%PYTHON%" tests\smoke_test.py
if errorlevel 1 exit /b 1

pause
exit /b 0

:setup_failed
echo.
echo ERROR: OmniPad environment setup failed. Smoke tests were not started.
pause
exit /b 1
