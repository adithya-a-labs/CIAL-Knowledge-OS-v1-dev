@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_qdrant.ps1" %*
exit /b %errorlevel%
