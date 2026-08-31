@echo off
title OmniPad Process Cleanup
echo Cleaning up any lingering OmniPad processes (cloudflared, orphaned python servers)...
taskkill /F /IM cloudflared.exe 2>nul
echo Done cleaning processes.
