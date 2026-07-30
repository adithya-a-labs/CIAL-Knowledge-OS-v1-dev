@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_lan_gateway.ps1" %*
exit /b %errorlevel%

