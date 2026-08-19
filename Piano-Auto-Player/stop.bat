@echo off
powershell -NoProfile -Command "$c = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue; if ($c) { Stop-Process -Id $c.OwningProcess -Force; Write-Host 'Piano Auto Player stopped.' } else { Write-Host 'Piano Auto Player is not running.' }"
pause
