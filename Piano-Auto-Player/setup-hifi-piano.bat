@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

echo ============================================================
echo Piano Auto Player - optional Hi-Fi piano engine setup
echo Transkun V2 lives in its own .piano-hifi-venv environment.
echo ============================================================
echo.

set "PYBASE="
where py >nul 2>nul
if not errorlevel 1 (
  py -3.10 -c "import sys; print(sys.executable)" >nul 2>nul && set "PYBASE=py -3.10"
  if not defined PYBASE py -3.11 -c "import sys; print(sys.executable)" >nul 2>nul && set "PYBASE=py -3.11"
  if not defined PYBASE py -3.12 -c "import sys; print(sys.executable)" >nul 2>nul && set "PYBASE=py -3.12"
)
if not defined PYBASE (
  where python >nul 2>nul || goto :no_python
  python -c "import sys; raise SystemExit(0 if (3,9) <= sys.version_info[:2] <= (3,12) else 1)" >nul 2>nul || goto :no_python
  set "PYBASE=python"
)

if not exist ".piano-hifi-venv\Scripts\python.exe" (
  echo Creating .piano-hifi-venv...
  %PYBASE% -m venv ".piano-hifi-venv" || goto :failed
)

set "HPY=%CD%\.piano-hifi-venv\Scripts\python.exe"
"%HPY%" -m pip install --upgrade pip setuptools wheel || goto :failed

echo.
echo Installing PyTorch runtime first...
set "TORCH_READY="
where nvidia-smi >nul 2>nul
if errorlevel 1 goto :cpu_torch

echo NVIDIA GPU detected. Trying the official CUDA 12.8 PyTorch wheels...
"%HPY%" -m pip install --upgrade torch torchaudio --index-url https://download.pytorch.org/whl/cu128
if not errorlevel 1 set "TORCH_READY=1"
if defined TORCH_READY goto :runtime_deps

echo WARNING: CUDA PyTorch install failed. Falling back to official CPU wheels.

:cpu_torch
"%HPY%" -m pip install --upgrade torch torchaudio --index-url https://download.pytorch.org/whl/cpu || goto :failed

:runtime_deps
echo.
echo Installing Transkun inference dependencies...
"%HPY%" -m pip install --upgrade pretty-midi mir-eval pydub soxr moduleconf || goto :failed

echo.
echo Installing Transkun V2 without its training-only ncls dependency...
"%HPY%" -m pip install --upgrade --no-deps "transkun==2.0.1" || goto :failed

echo.
echo Verifying Hi-Fi engine and pretrained model...
set "HDEVICE=cpu"
"%HPY%" -c "import torch; raise SystemExit(0 if torch.cuda.is_available() else 1)" >nul 2>nul
if not errorlevel 1 set "HDEVICE=cuda"

"%HPY%" -c "import importlib.metadata as m, torch, torchaudio, pretty_midi, mir_eval, pydub, soxr, moduleconf; import transkun.transcribe; print('Transkun', m.version('transkun')); print('Torch', torch.__version__); print('Torchaudio', torchaudio.__version__); print('Device', 'cuda' if torch.cuda.is_available() else 'cpu'); print('GPU', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU fallback')" || goto :failed
"%HPY%" -m app.transkun_bridge --probe --device !HDEVICE! || goto :failed

echo.
echo Hi-Fi piano engine is ready.
echo Restart start.bat, then choose Auto Hi-Fi in Media / Spotify - Piano.
echo Basic Pitch remains the fallback if the specialist is unavailable or disagrees strongly.
echo.
pause
exit /b 0

:no_python
echo.
echo ERROR: Python 3.9-3.12 is required for the optional Hi-Fi environment.
echo Python 3.10 is preferred for Transkun 2.0.1.
echo.
pause
exit /b 1

:failed
echo.
echo ERROR: Hi-Fi setup did not complete. The normal Basic Pitch engine is unchanged and will still work.
echo.
pause
exit /b 1
