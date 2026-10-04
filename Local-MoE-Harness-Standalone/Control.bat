@echo off
setlocal EnableExtensions
title Local MoE Harness Control
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\control-windows.ps1" %*
exit /b %ERRORLEVEL%
